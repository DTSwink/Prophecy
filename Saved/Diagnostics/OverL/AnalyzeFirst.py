import sys,pathlib,json,numpy as np
sys.path.insert(0,str(pathlib.Path('Saved/Diagnostics').resolve()))
from CompareRecoveryLegs import load,pose_metrics,direction_angle,rot,OFF,angle
p,q,m=load('PelvisHitch-20260921-172254')
rows=pose_metrics(q,115,177)
for r in rows:
 t=r['tick'];x=r['legs']['right'];print('PIPE',t,'weights',[q[t][k] for k in ['walk_weight','left_walk_weight','right_walk_weight']],'thigh/raw/corr',*[round(x[k],2) for k in ['thigh_direction_step_deg','raw_thigh_step_deg','raw_correction_deg']],'knee side/forward',*[round(x[k],2) for k in ['knee_side_cm','knee_forward_cm']],'distance',round(x['hip_ankle_cm'],2))
for t in range(119,146):
 r=m[t];a=m[t-1];out={}
 for mode in ['future','target','visible','body']:
  if mode not in r['bones']['thigh_r'] or mode not in a['bones']['thigh_r']:continue
  v=np.array(r['bones']['calf_r'][mode]['p'])-r['bones']['thigh_r'][mode]['p'];v0=np.array(a['bones']['calf_r'][mode]['p'])-a['bones']['thigh_r'][mode]['p'];out[mode]=round(direction_angle(v0,v),3)
 print('FRAME',t,'attack',r['attack'],'thighdir',out)
res={'pipe':rows}
(pathlib.Path('Saved/Diagnostics/OverL')/'first_capture_analysis.json').write_text(json.dumps(res,indent=2))
