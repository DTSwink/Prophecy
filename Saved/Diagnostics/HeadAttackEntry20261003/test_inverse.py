import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path(__file__).resolve().parent
rows={r['tick']:r for r in json.loads((p/'velocity_diagnosis.json').read_text())['rows']}
trace=next(r for r in (json.loads(l) for l in (p/'velocity_diagnosis-nn.jsonl').read_text().splitlines()) if r['actor'].endswith('_0') and r['frame']==2)
j=json.loads((p.parents[2]/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
names,parents,core=j['body_names'],j['parents_body'],j['core_bones'];mirror=np.diag([1,-1,1])
def decode(x):
 a=np.array(x[:3]);a/=np.linalg.norm(a);b=np.array(x[3:6]);b-=a*np.dot(a,b);b/=np.linalg.norm(b)
 return R.from_matrix(mirror@np.array([a,b,np.cross(a,b)]).T@mirror)
previous={n:decode(trace['input'][82+6*i:88+6*i]) for i,n in enumerate(core)}
current={n:decode(trace['input'][172+6*i:178+6*i]) for i,n in enumerate(core)}
base,end=rows[169]['bones'],rows[170]['bones'];q={'pelvis':R.from_quat(base['pelvis']['body']['q'])};errors={}
for n in names:
 if n in core:q[n]=q[names[parents[names.index(n)]]]*current[n]
for n in ('spine_05','head'):
 errors[n]=float(np.degrees((q[n].inv()*R.from_quat(base[n]['body']['q'])).magnitude()))
 assert errors[n]<1e-4,'Decoded physical seed does not match captured physical pose'
# Change velocity only: displayed start pose and parent-local attachments stay.
# Pelvis rotation/position at170 is exactly the original recorded value.
q={'pelvis':R.from_quat(end['pelvis']['presented']['q'])};pos={'pelvis':np.array(end['pelvis']['presented']['p'])}
for n in core[:8]:
 parent=names[parents[names.index(n)]];rq=R.from_quat(base[parent]['presented']['q']);v=base[n]['presented']
 local_q=rq.inv()*R.from_quat(v['q']);local_p=rq.inv().apply(np.array(v['p'])-base[parent]['presented']['p'])
 velocity=(current[n]*previous[n].inv()).as_rotvec()*30
 q[n]=q[parent]*R.from_rotvec(velocity/60)*local_q;pos[n]=pos[parent]+q[parent].apply(local_p)
entry=R.from_quat(trace['anchor'][3:])
def lateral(h,pel):return float(entry.inv().apply(np.array(h)-pel)[0])
start=lateral(base['head']['presented']['p'],base['pelvis']['presented']['p'])
original=lateral(end['head']['presented']['p'],end['pelvis']['presented']['p'])
inverse=lateral(pos['head'],pos['pelvis'])
prior=rows[168]['bones'];prior_step=start-lateral(prior['head']['presented']['p'],prior['pelvis']['presented']['p'])
result={'method':'Single-frame counterfactual; physical core angular velocity; original pelvis; no live code change or physical rerun',
 'physical_seed_decode_max_error_degrees':errors,'previous_target_lateral_step_cm':prior_step,
 'original_target_169_to_170_lateral_step_cm':original-start,'inverse_target_169_to_170_lateral_step_cm':inverse-start}
print(json.dumps(result,indent=2));(p/'inverse-velocity-analysis.json').write_text(json.dumps(result,indent=2))
