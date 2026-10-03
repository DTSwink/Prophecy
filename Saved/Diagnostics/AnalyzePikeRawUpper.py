import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/Knee202');c=json.load(open('Content/locomotion/NN/prophecy_upper_body_runtime.json'))
names=c['body_names'];parents=c['parents_body'];offsets=np.array(c['local_offsets_m']);mirror=np.diag([1,-1,1])
seed=np.array(json.load(open('Content/locomotion/NN/prophecy_lower_body_runtime.json'))['seed_root_rotation_rows'])
def unit(v):return v/max(np.linalg.norm(v),1e-12)
def rot6(x):
 a=unit(x[:3]);b=unit(x[3:6]-a*np.dot(a,x[3:6]));return np.array([a,b,np.cross(a,b)])
def decode(t):
 inp=np.array(t['upper_input']);u=inp[90:180]+t['upper_delta'];lower=np.array(t['published_lower']);pos={0:lower[:3]@seed};rot={0:rot6(lower[3:9])@seed}
 for name in c['core_bones']:
  i=names.index(name);par=parents[i];j=c['core_bones'].index(name)
  pos[i]=pos[par]+offsets[i]@rot[par];rot[i]=rot6(u[j*6:j*6+6])@rot[par]
 i=names.index('upperarm_r');par=parents[i];s=pos[par]+offsets[i]@rot[par];q=rot6(u[84:90]);e=s+offsets[names.index('lowerarm_r')]@q;h=u[75:78]
 spine=names.index('spine_05');clav=names.index('clavicle_r')
 local=lambda v:((v-pos[spine])@rot[spine].T)@mirror
 qsp=R.from_matrix((mirror@q@rot[spine].T@mirror).T)
 qlocal=R.from_matrix((mirror@q@rot[clav].T@mirror).T)
 return [local(v)*100 for v in (s,e,h)],qsp,qlocal
def pole(v):
 s,e,h=np.array(v);ax=unit(h-s);return ax,unit(e-s-ax*np.dot(e-s,ax))
def turn(a,b):
 x,v=pole(a);y,w=pole(b);v=unit(v-(x+y)*np.dot(v,y)/max(1+np.dot(x,y),1e-8))
 return float(np.degrees(np.arctan2(np.dot(y,np.cross(v,w)),np.dot(v,w))))
report={}
for mode in ('baseline','exit_no_inertia'):
 cap=json.loads((p/f'pike_elbow_{mode}.json').read_text())['rows'];traces=[json.loads(x) for x in (p/f'pike_elbow_{mode}_nn.jsonl').read_text().splitlines()]
 out=[]
 for t in traces:
  if t['attack'] or t['actor']!=cap[0]['actor']:continue
  row=min(cap,key=lambda r:abs(r['t']-t['time']));tick=row['tick']
  if not 171<=tick<=215:continue
  v,q,qcl=decode(t);b=row['raw'];qr=lambda n:R.from_quat(b[n]['future']['q'])
  actual=qr('spine_05').inv()*qr('upperarm_r');actlocal=qr('clavicle_r').inv()*qr('upperarm_r')
  out.append(dict(tick=tick,positions=[x.tolist() for x in v],upperarm_vs_final_deg=float(np.degrees((q.inv()*actual).magnitude())),upperarm_local_vs_final_deg=float(np.degrees((qcl.inv()*actlocal).magnitude()))))
 total=sum(turn(a['positions'],b['positions']) for a,b in zip(out,out[1:]))
 print(mode,'NN pole travel173-215',total,'max arm error',max(r['upperarm_vs_final_deg'] for r in out));print([{k:v for k,v in r.items() if k!='positions'} for r in out[:5]])
 report[mode]=dict(nn_pole_travel_deg=total,rows=out)
(p/'pike_raw_upper_analysis.json').write_text(json.dumps(report,indent=2))

