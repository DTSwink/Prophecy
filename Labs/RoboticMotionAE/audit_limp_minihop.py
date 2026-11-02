"""Read-only support-foot settling audit from an existing recorded rollout."""
import json,itertools,shutil
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitSlowLoco/minihop-audit-20261101'
RUN=json.loads((ROOT/'Saved/MimicKitSlowLoco/active_run.json').read_text())['run']
SOURCE=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+RUN)/'replay.npz'
OUT.mkdir(exist_ok=True);shutil.copy2(SOURCE,OUT/'latest-replay.npz')
GEOM=json.loads((ROOT/'Saved/MimicKitSlowLoco/geometry.json').read_text())
def segments(mask):
    edges=np.diff(np.r_[False,mask,False].astype(int));return list(zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)))
report={};series={}
with np.load(OUT/'latest-replay.npz',allow_pickle=False) as z:
 meta=json.loads(str(z['metadata']));step=meta['iteration']
 for name,foot in [('limpL','right_foot'),('limpR','left_foot')]:
  i=next(i for i,r in enumerate(meta['replay_rows']) if r['motion_name']==name);r=meta['replay_rows'][i];suffix='_'+str(i);j=r['names'].index(foot)
  pose=z['pose'+suffix];ref=z['reference_pose'+suffix];vel=z['world_velocities'+suffix];terms=z['loss_terms'+suffix]
  shape=next(s for s in GEOM['shapes'] if s['bone']==foot);off=np.array(shape['position']);axes=np.array(shape['axes']);half=np.array(shape['dimensions'])/2
  corners=np.array(list(itertools.product([-1,1],repeat=3)))*half@axes+off
  R=Rotation.from_quat(pose[:,j,3:]).as_matrix();T=Rotation.from_quat(ref[:,j,3:]).as_matrix()
  offset=np.einsum('tij,j->ti',R,off);toffset=np.einsum('tij,j->ti',T,off)
  center=pose[:,j,:3]+offset;tc=ref[:,j,:3]+toffset
  height=(pose[:,j,None,:3]+np.einsum('tij,cj->tci',R,corners))[:,:,2].min(-1)
  th=(ref[:,j,None,:3]+np.einsum('tij,cj->tci',T,corners))[:,:,2].min(-1)
  cv=vel[:,j,:3]+np.cross(vel[:,j,3:6],offset);tv=vel[:,j,6:9]+np.cross(vel[:,j,9:12],toffset)
  speed=np.linalg.norm(cv,axis=-1);ts=np.linalg.norm(tv,axis=-1)
  error=np.linalg.norm(pose[:,j,:3]-ref[:,j,:3],axis=-1)
  angle=Rotation.from_matrix(np.einsum('tji,tjk->tik',T,R)).magnitude()
  normal=np.einsum('tij,j->ti',R,axes[0]);tn=np.einsum('tij,j->ti',T,axes[0]);tilt=np.arccos(np.clip((normal*tn).sum(-1),-1,1))
  pc=np.maximum(error-.1,0)**2/45*r['loss_weights']['position_mse']
  rc=8*np.sin(np.maximum(angle-np.deg2rad(15),0)/2)**2/135*r['loss_weights']['rotation_mse']
  lc=((vel[:,j,:3]-vel[:,j,6:9])**2).sum(-1)/45*r['loss_weights']['linear_velocity_mse']
  ac=((vel[:,j,3:6]-vel[:,j,9:12])**2).sum(-1)/45*r['loss_weights']['angular_velocity_mse']
  flights=[(a,b) for a,b in segments(height>.01) if b-a>=2]
  events=[]
  for a,b in flights:
   if b<35 or b+12>=len(height):continue
   # First recorded frame where any foot corner has returned to <=5mm.
   candidates=np.flatnonzero(height[b:]<=.005)
   if not len(candidates):continue
   land=b+int(candidates[0]);window=np.arange(land+2,min(land+11,len(speed)))
   k=int(window[np.argmax(speed[window])])
   events.append(dict(touchdown=land,burst_frame=k,center_speed_m_s=float(speed[k]),target_speed_m_s=float(ts[k]),
      foot_bottom_cm=float(height[k]*100),foot_center_cm=float(center[k,2]*100),position_error_cm=float(error[k]*100),
      orientation_error_deg=float(np.rad2deg(angle[k])),sole_tilt_error_deg=float(np.rad2deg(tilt[k])),
      position_loss=float(pc[k]),rotation_loss=float(rc[k]),linear_velocity_loss=float(lc[k]),angular_velocity_loss=float(ac[k]),
      total_loss=float(terms[k,:5].sum()),settling_velocity_loss_sum=float((lc+ac)[window].sum()),
      center_horizontal_shift_cm=float(np.linalg.norm(center[land+10,:2]-center[land+1,:2])*100)))
  report[name]=dict(active_foot=foot,frames=len(height),flight_intervals=flights,postlanding_events=events,
    median_settling_peak_speed_m_s=float(np.median([e['center_speed_m_s'] for e in events])),
    median_settling_velocity_loss_sum=float(np.median([e['settling_velocity_loss_sum'] for e in events])))
  series[name]=dict(speed=speed,target_speed=ts,height=height,target_height=th,center=center,target_center=tc,
    position_cost=pc,rotation_cost=rc,linear_cost=lc,angular_cost=ac,tilt_deg=np.rad2deg(tilt),angle_deg=np.rad2deg(angle),error=error)
  np.savez(OUT/f'{step}-{name}-speed.npz',**series[name])
report=dict(checkpoint=step,run=RUN,method='Stored world body-origin linear/angular velocities transported to foot collider centre; lowest oriented-box corner; 30Hz capture. No solver contact-force claim.',motions=report)
(OUT/'speed-audit.json').write_text(json.dumps(report,indent=2,default=lambda x:x.item()))
fig,axs=plt.subplots(2,2,figsize=(12,7),layout='constrained')
for col,name in enumerate(('limpL','limpR')):
 d=series[name];ax=axs[0,col];t=np.arange(len(d['speed']));ax.plot(t,d['speed'],label='Agent',lw=1.5);ax.plot(t,d['target_speed'],label='Reference',alpha=.8,lw=1)
 for e in report['motions'][name]['postlanding_events']:
  k=e['burst_frame'];ax.scatter(k,d['speed'][k],s=24,c='#d34c2f',zorder=4)
 ax.set(title=f"{name}: active {report['motions'][name]['active_foot']}",xlabel='Rollout frame',ylabel='Foot centre speed (m/s)',ylim=(0,4.5));ax.grid(alpha=.2);ax.legend()
 events=report['motions'][name]['postlanding_events'];e=min(events,key=lambda e:abs(e['touchdown']-140));land=e['touchdown'];t=np.arange(land,min(land+15,len(d['speed'])));ax=axs[1,col]
 ax.plot(t-land,d['speed'][t],marker='o',label='Agent');ax.plot(t-land,d['target_speed'][t],label='Reference');ax.set(title=f"After touchdown at frame {land}",xlabel='Frames after touchdown',ylabel='Foot centre speed (m/s)',ylim=(0,2));ax.grid(alpha=.2);ax.legend()
fig.suptitle(f'Support-foot settling — checkpoint {step} (30 fps)',fontsize=15)
fig.savefig(OUT/'foot-speed.png',dpi=150);plt.close(fig)
print(json.dumps(report,indent=2,default=lambda x:x.item()))
