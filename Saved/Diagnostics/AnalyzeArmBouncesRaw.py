import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics/Knee202')
c=json.load(open('Content/locomotion/NN/prophecy_upper_body_runtime.json'));names=c['body_names'];parents=c['parents_body'];offsets=np.array(c['local_offsets_m'])
seed=np.array(json.load(open('Content/locomotion/NN/prophecy_lower_body_runtime.json'))['seed_root_rotation_rows'])
def unit(v):return v/max(np.linalg.norm(v),1e-12)
def rot6(x):
 a=unit(x[:3]);b=unit(x[3:6]-a*np.dot(a,x[3:6]));return np.array([a,b,np.cross(a,b)])
def decode(t):
 inp=np.array(t['upper_input']);u=inp[90:180]+t['upper_delta'];lo=np.array(t['published_lower']);pos={0:lo[:3]@seed};rot={0:rot6(lo[3:9])@seed}
 for name in c['core_bones']:
  i=names.index(name);par=parents[i];j=c['core_bones'].index(name);pos[i]=pos[par]+offsets[i]@rot[par];rot[i]=rot6(u[j*6:j*6+6])@rot[par]
 def shoulder(side):
  i=names.index('upperarm_'+side);par=parents[i];return pos[par]+offsets[i]@rot[par]
 s=shoulder('l');right=shoulder('r');e=s+offsets[names.index('lowerarm_l')]@rot6(u[69:75]);h=u[60:63]
 out=unit(s-right);up=unit(pos[names.index('spine_05')]-pos[0]);up=unit(up-out*np.dot(up,out));basis=np.array([out,np.cross(out,up),up])
 return dict(elbow=(basis@(e-s)*100).tolist(),hand=(basis@(h-s)*100).tolist(),length=float(np.linalg.norm(h-e)*100))
rows=json.load(open(p/'arm_bounces_trace.json'))['rows'];records=[]
for line in (p/'arm_bounces_trace_nn.jsonl').read_text().splitlines():
 t=json.loads(line)
 if t['actor']!=rows[0]['actor'] or t['attack']:continue
 r=min(rows,key=lambda x:abs(x['t']-t['time']));tick=r['tick']
 if not any(a<=tick<=b for a,b in [(193,225),(359,393),(537,579)]):continue
 d=decode(t);d['tick']=tick;records.append(d)
 print(tick,'raw elbow',np.round(d['elbow'],2),'hand',np.round(d['hand'],2),'length',round(d['length'],2))
(p/'arm_bounces_raw_analysis.json').write_text(json.dumps(records,indent=2))
