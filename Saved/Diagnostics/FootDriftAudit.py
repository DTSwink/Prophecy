"""Read-only per-kick lateral-foot attribution in the pelvis heading frame."""
import json,pathlib,sys,math,numpy as np
from ReplayTemperedLeg import points,unit,rot,clean,mixstate,mixrot,config
p=pathlib.Path(sys.argv[1]);groups={};kick=0;was=False;last=None;series=[]
for line in (p/'metrics.jsonl').open():
 r=json.loads(line)
 if r['agent']!='BP_ProphecyManualPoseAgent_C_1':continue
 groups.setdefault(r['frame'],{})[r['side']]=r
for frame,pair in groups.items():
 if 'l' not in pair or 'r' not in pair:continue
 l=pair['l'];rr=pair['r'];attack=bool(l['attack'])
 if attack and not was:kick+=1
 was=attack
 if not kick:continue
 h,k,a,t=np.array(l['poses']['future']['points']);rh,rk,ra,rt=np.array(rr['poses']['future']['points'])
 right=unit((rh-h)*[1,1,0]);centre=(h+rh)*.5
 item=dict(kick=kick,frame=frame,time=l['time'],attack=attack,policy_frame=l['attack'][-1] if attack else None,
  inward_from_hip_cm=float(np.dot(a-h,right)),from_centre_cm=float(np.dot(a-centre,right)),
  foot_separation_cm=float(np.dot(ra-a,right)),ankle_z_cm=a[2],pelvis_height_proxy_cm=centre[2],
  descending=bool(last is not None and a[2]<last['ankle_z_cm']-.01))
 series.append(item);last=item
report=[]
for i in sorted(set(r['kick'] for r in series)):
 rows=[r for r in series if r['kick']==i];att=[r for r in rows if r['attack']];rec=[r for r in rows if not r['attack']]
 report.append(dict(kick=i,start=att[0] if att else None,last_attack=att[-1] if att else None,
  attack_peak_inward=max(att,key=lambda r:r['inward_from_hip_cm']) if att else None,
  recovery_peak_inward=max(rec,key=lambda r:r['inward_from_hip_cm']) if rec else None,
  end=rows[-1]))
trace=[];kick=0;was=False
for line in (p/'pipeline.jsonl').open():
 r=json.loads(line)
 if r['actor']!='BP_ProphecyManualPoseAgent_C_1':continue
 if r['attack'] and not was:kick+=1
 was=r['attack']
 if not kick or was or 'tempering' not in r:continue
 pub=np.array(r['published_lower']);prev=np.array(r['previous_lower']);current=np.array(r['lower_input'][:41]);settings=r['tempering']
 def tempered(delta):
  raw=clean(current+np.array(delta[:41]));out=raw.copy()
  for o,w in ((0,settings[2]),(9,settings[0]),(25,settings[0])):out[o:o+3]=prev[o:o+3]*(1-w)+out[o:o+3]*w
  for o,w in ((3,settings[3]),(12,settings[1]),(28,settings[1])):out[o:o+6]=mixrot(rot(prev,o),rot(out,o),w)[:2].ravel()
  return raw,out
 raw,before=tempered(r['lower_delta']);run_raw=raw.copy();walk_raw=None
 if 'walk_delta' in r:
  wr,wt=tempered(r['walk_delta']);walk_raw=wr;raw=mixstate(raw,wr,r['walk_weight']);before=mixstate(before,wt,r['walk_weight'])
 h,_,a,t=points(pub);rh,*_=points(pub,1);right=unit((rh-h)*[1,1,0]);fw=unit((t-a)*[1,1,0]);side=np.cross([0,0,1],fw)
 bh,_,ba,bt=points(before);delta=ba-bh;sag=delta-side*np.dot(delta,side)
 correction=unit(sag)*max(0,.15-np.linalg.norm(sag));expected=ba+correction
 trace.append(dict(kick=kick,time=r['time'],raw_inward_cm=float(np.dot(points(raw)[2]-points(raw)[0],right)*100),
  previous_inward_cm=float(np.dot(points(prev)[2]-points(prev)[0],right)*100),
  run_prediction_inward_cm=float(np.dot(points(run_raw)[2]-points(run_raw)[0],right)*100),
  walk_prediction_inward_cm=float(np.dot(points(walk_raw)[2]-points(walk_raw)[0],right)*100) if walk_raw is not None else None,
  tempered_before_pin_inward_cm=float(np.dot(ba-bh,right)*100),published_inward_cm=float(np.dot(a-h,right)*100),
  inner_clearance_correction_inward_cm=float(np.dot(correction,right)*100),
  leftover_correction_cm=float(np.linalg.norm(a-expected)*100),
  sagittal_distance_before_cm=float(np.linalg.norm(sag)*100),walk_weight=r['walk_weight'],
  run_pin_raw=r['lower_delta'][41],walk_pin_raw=r.get('walk_delta',[0]*43)[41],settings=settings))
out=dict(kicks=report,trace=trace)
(p/'foot-drift.json').write_text(json.dumps(out,indent=2))
for r in report[:10]:
 print('KICK',r['kick'],{key:round(r[key]['inward_from_hip_cm'],2) if r[key] else None for key in ('start','last_attack','attack_peak_inward','recovery_peak_inward','end')})
for i in (1,2,3,4,10):
 rs=[r for r in trace if r['kick']==i]
 if rs:print('RECOVERY_PEAK',json.dumps(max(rs,key=lambda r:r['published_inward_cm'])))
