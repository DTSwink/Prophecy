import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path(__file__).resolve().parent
layout=json.loads((p.parents[2]/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
def rows(n):return {r['tick']:r for r in json.loads((p/(n+'.json')).read_text())['rows']}
a,b,k=rows('sync_physical'),rows('sync_physical_nn_seed_off'),rows('sync_kinematic')
trace=next(r for r in (json.loads(l) for l in (p/'sync_physical-nn.jsonl').read_text().splitlines()) if r['actor'].endswith('_0') and r['frame']==2)
mirror=np.diag([1,-1,1])
def decode(x):
 u=np.array(x[:3]);u/=np.linalg.norm(u);v=np.array(x[3:]);v-=u*np.dot(u,v);v/=np.linalg.norm(v)
 return R.from_matrix(mirror@np.array([u,v,np.cross(u,v)]).T@mirror)
def local(rs,t,n,kind):
 parent=layout['body_names'][layout['parents_body'][layout['body_names'].index(n)]]
 return R.from_quat(rs[t]['bones'][parent][kind]['q']).inv()*R.from_quat(rs[t]['bones'][n][kind]['q'])
phys_errors=[];kin_errors=[];toggle_errors=[]
for i,n in enumerate(layout['core_bones']):
 old=decode(trace['input'][82+6*i:88+6*i]);cur=decode(trace['input'][172+6*i:178+6*i]);expected=R.from_rotvec((cur*old.inv()).as_rotvec()*.5)*cur
 phys_errors.append(np.degrees((expected.inv()*local(a,170,n,'presented')).magnitude()))
 kin_errors.append(np.degrees((local(k,169,n,'future').inv()*local(k,170,n,'presented')).magnitude()))
 toggle_errors.append(np.degrees((local(a,170,n,'presented').inv()*local(b,170,n,'presented')).magnitude()))
expected=R.from_rotvec(np.array(a[169]['bones']['pelvis']['angular_velocity'])/60)*R.from_quat(a[169]['bones']['pelvis']['body']['q'])
physical_pelvis_error=np.degrees((expected.inv()*R.from_quat(a[170]['bones']['pelvis']['presented']['q'])).magnitude())
old=R.from_quat(k[167]['bones']['pelvis']['future']['q']);cur=R.from_quat(k[169]['bones']['pelvis']['future']['q']);expected=R.from_rotvec((cur*old.inv()).as_rotvec()*.5)*R.from_quat(k[169]['bones']['pelvis']['presented']['q'])
kin_pelvis_error=np.degrees((expected.inv()*R.from_quat(k[170]['bones']['pelvis']['presented']['q'])).magnitude())
result={'physical_mode':a[170]['simulation_mode'],'kinematic_mode':k[170]['simulation_mode'],'physical_core_error_degrees':max(phys_errors),'physical_pelvis_error_degrees':physical_pelvis_error,'kinematic_core_error_degrees':max(kin_errors),'kinematic_pelvis_error_degrees':kin_pelvis_error,'physical_core_error_when_NN_seed_disabled_degrees':max(toggle_errors)}
for n,v in result.items():
 if n.endswith('degrees'):assert v<1e-4,(n,v)
(p/'sync-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
