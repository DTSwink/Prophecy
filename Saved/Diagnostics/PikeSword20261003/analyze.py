import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).parent;root=p.parents[2]
meta=json.loads((root/'Content/locomotion/NN/prophecy_slash_runtime.json').read_text());names=meta['bone_names'];hi=names.index('hand_r')
geometry=json.loads((p/'geometry.json').read_text());tip=np.array([0,0,geometry['max'][2]])
base=json.loads((p/'baseline.json').read_text());grip=base['metadata']['sword_grip'];tip_hand=R.from_quat(grip['q']).apply(tip*grip['s'])+grip['p'];mirror=np.diag([1,-1,1])
def point(transform,local=tip_hand):return np.array(transform['p'])+R.from_quat(transform['q']).apply(local)
def groups(trace):
 out=[]
 for r in trace:
  if not out or r['frame']<=out[-1][-1]['frame']:out.append([])
  out[-1].append(r)
 return out
def native(row):
 out=np.array(row['output']);source=np.array(row['native_rotation']).reshape(3,3);carrier=R.from_quat(row['anchor'][3:]).as_matrix()
 positions=((out[131:206].reshape(25,3)-row['native_position'])@source.T@mirror*100)@carrier.T+row['anchor'][:3]
 rots=carrier@mirror@source@out[206:431].reshape(25,3,3).transpose(0,2,1)@mirror
 target=(np.array(row['input'][262:265])-row['native_position'])@source.T@mirror*100@carrier.T+row['anchor'][:3]
 return positions,R.from_matrix(rots),target
def metrics(points,direction):
 d=np.diff(points,axis=0);along=d@direction;side=d-along[:,None]*direction
 lateral=(points-points[0])-((points-points[0])@direction)[:,None]*direction
 return dict(path_cm=float(np.linalg.norm(d,axis=1).sum()),net_cm=float(np.linalg.norm(points[-1]-points[0])),lateral_path_cm=float(np.linalg.norm(side,axis=1).sum()),lateral_range_cm=float(np.linalg.norm(lateral,axis=1).max()),max_step_cm=float(np.linalg.norm(d,axis=1).max()),max_velocity_change=float(np.linalg.norm(np.diff(d,axis=0),axis=1).max()))
allreports={};rawdata={};fig,axs=plt.subplots(2,3,figsize=(16,9),constrained_layout=True)
baseline_rows={r['tick']:r for r in base['rows']}
for file in p.glob('*-nn.jsonl'):
 name=file.name.removesuffix('-nn.jsonl');data=json.loads((p/(name+'.json')).read_text());rows=data['rows'];bytick={r['tick']:r for r in rows};trace=[r for r in map(json.loads,file.read_text().splitlines()) if r['actor']=='BP_ProphecyManualPoseAgent_C_0'];sections=groups(trace);report=[]
 for ordinal,g in enumerate(sections,1):
  active=[r for r in rows if r['attack_count']==ordinal and r['attack']];pts=[];qs=[];targets=[];ticks=[]
  for z in g:
   pos,q,tgt=native(z);pts.append(pos[hi]+q[hi].apply(tip_hand));qs.append(q[hi].as_quat());targets.append(tgt);ticks.append(round(z['time']*60))
  pts=np.array(pts);targets=np.array(targets);direction=targets[0]-pts[0];direction/=np.linalg.norm(direction)
  entry=dict(ordinal=ordinal,start=active[0]['tick'],end=active[-1]['tick'],target_travel_cm=float(np.linalg.norm(np.diff(targets,axis=0),axis=1).sum()),native=metrics(pts,direction),paths={})
  for kind in ('future','presented','body'):
   points=np.array([point(r['bones']['hand_r'][kind]) for r in active]);q=R.from_quat([r['bones']['hand_r'][kind]['q'] for r in active]);entry['paths'][kind]=metrics(points,direction);entry['paths'][kind]['angular_path_deg']=float(np.degrees((q[:-1].inv()*q[1:]).magnitude()).sum())
  actual=np.array([point(r['sword_components']['sword'],tip*np.array(r['sword_components']['sword']['s'])) for r in active]);entry['paths']['sword_actual']=metrics(actual,direction)
  future_error=[];rotation_error=[]
  for z,tick in zip(g,ticks):
   pos,q,_=native(z);f=bytick[tick]['bones']['hand_r']['future'];future_error.append(float(np.linalg.norm(point(f)-(pos[hi]+q[hi].apply(tip_hand)))));rotation_error.append(float(np.degrees((q[hi].inv()*R.from_quat(f['q'])).magnitude())))
  entry['native_to_future_tip_error_cm']=future_error;entry['native_to_future_hand_rotation_deg']=rotation_error
  report.append(entry)
  if ordinal==2:
   up=np.array([0,0,1]);side=np.cross(up,direction);side/=np.linalg.norm(side)
   if name=='baseline':origin=pts[0];basis=np.array([side,np.cross(direction,side),direction])
   rawdata[name]=dict(active=active,pts=pts,ticks=ticks,target=targets,direction=direction)
 allreports[name]=dict(reason=data['reason'],attacks=report)
 print(name,'second tip lateral range',round(report[1]['paths']['presented']['lateral_range_cm'],3),'native/future rotation error',round(max(report[1]['native_to_future_hand_rotation_deg']),3),flush=True)
 # Prefix includes the triggering frame; all interventions happen after capture.
 if name!='baseline':allreports[name]['prefix_max_cm']=max(np.linalg.norm(np.array(r['bones'][b]['presented']['p'])-baseline_rows[r['tick']]['bones'][b]['presented']['p']) for r in rows if r['tick']<=342 for b in r['bones'])
base2=rawdata['baseline'];origin=base2['pts'][0];direction=base2['direction'];side=np.cross([0,0,1],direction);side/=np.linalg.norm(side);basis=np.array([side,np.cross(direction,side),direction])
for name,v in rawdata.items():
 if name not in ('baseline','drag_off','hands_off','entry_off','clean_attack'):continue
 for j,kind in enumerate(('native','presented','body')):
  if kind=='native':points=v['pts'];ticks=v['ticks']
  else:points=np.array([point(r['bones']['hand_r'][kind]) for r in v['active']]);ticks=[r['tick'] for r in v['active']]
  local=(points-origin)@basis.T
  axs[0,j].plot(local[:,2],local[:,0],'.-',label=name,markersize=3)
  axs[1,j].plot(ticks,local[:,1],'.-',label=name,markersize=3)
  axs[0,j].set_title(kind+' blade endpoint');axs[0,j].set_xlabel('Toward target (cm)');axs[0,j].set_ylabel('Sideways (cm)')
  axs[1,j].set_xlabel('Game tick');axs[1,j].set_ylabel('Vertical across target ray (cm)')
for ax in axs.flat:ax.grid(alpha=.25);ax.legend(fontsize=8)
fig.savefig(p/'second-pike-paths.png',dpi=135)
(p/'analysis.json').write_text(json.dumps(allreports,indent=2))
