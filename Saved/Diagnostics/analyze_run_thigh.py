import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation
folder=pathlib.Path('Saved/Diagnostics/RunHandThigh');capture=json.loads((folder/'baseline.json').read_text())
rows=capture['rows'];c=json.load(open('Content/locomotion/NN/prophecy_upper_body_runtime.json'))
names=c['body_names'];parents=c['parents_body'];off=np.asarray(c['local_offsets_m']);seed=np.asarray(json.load(open('Content/locomotion/NN/prophecy_lower_body_runtime.json'))['seed_root_rotation_rows']);mirror=np.diag([1,-1,1])
def unit(v):return v/max(np.linalg.norm(v),1e-12)
def rot6(v):
 a=unit(v[:3]);b=unit(v[3:6]-a*np.dot(a,v[3:6]));return np.array([a,b,np.cross(a,b)])
def segdist(p,a,b):
 d=b-a;f=np.clip(np.dot(p-a,d)/max(np.dot(d,d),1e-12),0,1);return float(np.linalg.norm(p-a-f*d))
def dist(pose):return segdist(np.array(pose['hand_l']['p']),np.array(pose['thigh_r']['p']),np.array(pose['calf_r']['p']))
def decode(t,u):
 lower=np.asarray(t['published_lower']);pos={0:lower[:3]@seed};rot={0:rot6(lower[3:9])@seed}
 for j,name in enumerate(c['core_bones']):
  i=names.index(name);par=parents[i];pos[i]=pos[par]+off[i]@rot[par];rot[i]=rot6(u[j*6:j*6+6])@rot[par]
 for side,base in [('l',60),('r',75)]:
  i=names.index('upperarm_'+side);e=names.index('lowerarm_'+side);h=names.index('hand_'+side);par=parents[i]
  pos[i]=pos[par]+off[i]@rot[par];rot[i]=rot6(u[base+9:base+15]);pos[e]=pos[i]+off[e]@rot[i];pos[h]=u[base:base+3];rot[h]=rot6(u[base+3:base+9])
 return pos,rot
out=[]
traces=[json.loads(s) for s in (folder/'baseline_nn.jsonl').read_text(encoding='utf-8-sig').splitlines() if s.strip()]
for t in traces:
 if not rows or t['actor']!=rows[0]['actor']:continue
 r=min(rows,key=lambda r:abs(r['time']-t['time']))
 if abs(r['time']-t['time'])>.02:continue
 u=np.array(t['upper_input'][90:180])+t['upper_delta'];p,q=decode(t,u);h=names.index('hand_l');e=names.index('lowerarm_l')
 worldq=Rotation.from_quat(r['future']['pelvis']['q']).as_matrix()
 def world(v):return (v-p[0])@q[0].T@mirror@worldq.T*100+np.array(r['future']['pelvis']['p'])
 raw=world(p[h]);fixed=world(p[e]+unit(p[h]-p[e])*c['arm_limb_lengths_m'][0][1]);actual=np.array(r['future']['hand_l']['p'])
 a=np.array(r['future']['thigh_r']['p']);b=np.array(r['future']['calf_r']['p'])
 out.append(dict(tick=r['tick'],time=r['time'],attack=t['attack'],sword=r['sword'],sword_input=t['upper_input'][242],walk_weight=t['walk_weight'],future_cm=dist(r['future']),presented_cm=dist(r['presented']),mesh_cm=dist(r['mesh']),raw_cm=segdist(raw,a,b),fixed_cm=segdist(fixed,a,b),final_vs_fixed_cm=float(np.linalg.norm(fixed-actual)),raw_forearm_cm=float(np.linalg.norm(p[h]-p[e])*100),projection_cm=float(np.linalg.norm(raw-fixed)),hand=actual.tolist()))
report=dict(error=capture['error'],frames=len(rows),nn_frames=len(out),attack_frames=sum(x['attack'] for x in out),minima={k:min(out,key=lambda x:x[k]) for k in ['future_cm','presented_cm','mesh_cm']},max_post_decode_cm=max(x['final_vs_fixed_cm'] for x in out),sword_values=sorted(set(x['sword_input'] for x in out)),worst=sorted(out,key=lambda x:x['future_cm'])[:12])
(folder/'baseline_analysis.json').write_text(json.dumps(dict(summary=report,rows=out),indent=2))
print(json.dumps(report,indent=2))
