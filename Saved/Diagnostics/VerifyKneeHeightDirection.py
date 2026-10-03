import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics')
rows=json.loads((p/'SupportingKneeLead-live.json').read_text())['rows']
unit=lambda v:v/max(np.linalg.norm(v),1e-12)
yaw=lambda v:float(np.degrees(np.arctan2(v[1],v[0])))
wrap=lambda x:(x+180)%360-180
out=[]
# Frozen recorded world-space endpoints: no changed NN rollout can hide this error.
for r in rows:
 if not 162<=r['tick']<=166:continue
 b=r['targets'];hip,knee,foot,toe=[np.array(b[n+'_r']['p']) for n in ('thigh','calf','foot','ball')]
 axis=unit(foot-hip);upper=knee-hip;along=upper@axis;radial=upper-axis*along;radius=np.linalg.norm(radial)
 forward=unit((toe-foot)*[1,1,0]);side=np.cross([0,0,1],forward);normal=unit(side-axis*(side@axis))
 ground_pole=unit(np.cross(axis,normal));fixed_knee=hip+axis*along+ground_pole*radius
 assert abs(np.linalg.norm(fixed_knee-hip)-np.linalg.norm(upper))<1e-9
 assert abs(np.linalg.norm(fixed_knee-foot)-np.linalg.norm(knee-foot))<1e-9
 assert abs(wrap(yaw(ground_pole)-yaw(forward)))<1e-8
 out.append(dict(tick=r['tick'],foot_yaw=yaw(forward),old_pole_yaw=yaw(radial),new_pole_yaw=yaw(ground_pole),knee_change_cm=float(np.linalg.norm(fixed_knee-knee))))
# Interpolation is on the same knee circle, with zero derivative at height endpoints.
for q in np.linspace(-1,1,201):
 last=None
 for height in np.linspace(.02,.12,1001):
  t=np.clip((height-.02)/.10,0,1);support=1-t*t*(3-2*t)
  angle=np.arcsin(q)*(1-support);pole=np.array([np.sin(angle),np.cos(angle)])
  assert abs(np.linalg.norm(pole)-1)<1e-12
  if last is not None:assert np.linalg.norm(pole-last)<.00236
  last=pole
 assert np.allclose(last,[q,np.sqrt(max(0,1-q*q))])
result=dict(frozen=out,old_extra_turn_deg=wrap((out[-1]['old_pole_yaw']-out[0]['old_pole_yaw'])-(out[-1]['foot_yaw']-out[0]['foot_yaw'])),new_extra_turn_deg=wrap((out[-1]['new_pole_yaw']-out[0]['new_pole_yaw'])-(out[-1]['foot_yaw']-out[0]['foot_yaw'])),height_sweep_cases=201201)
(p/'KneeHeightDirection-frozen.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
