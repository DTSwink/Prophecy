import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation as R
ns={};exec(pathlib.Path('Saved/Diagnostics/AnalyzePikeRawUpper.py').read_text().split('report={}')[0],ns)
p=pathlib.Path('Saved/Diagnostics/Knee202');c=ns['c'];mirror=ns['mirror'];rot6=ns['rot6'];axis=np.array(c['local_offsets_m'][c['body_names'].index('hand_r')]);axis/=np.linalg.norm(axis)
report={}
for mode in ('current','no_cone','exit_no_inertia'):
 rows=json.loads((p/f'arm_revolution_{mode}.json').read_text())['rows'];traces=[json.loads(l) for l in (p/f'arm_revolution_{mode}_nn.jsonl').read_text().splitlines()];out=[]
 for t in traces:
  if t['attack'] or t['actor']!=rows[0]['actor']:continue
  row=min(rows,key=lambda r:abs(r['t']-t['time']))
  if not 189<=row['tick']<=229:continue
  u=np.array(t['upper_input'][90:180])+t['upper_delta'];qarm=R.from_matrix(rot6(u[84:90]).T);qhand=R.from_matrix(rot6(u[78:84]).T)
  lower=np.array(t['published_lower']);seed=ns['seed'];pos={0:lower[:3]@seed};rot={0:rot6(lower[3:9])@seed};names=ns['names'];parents=ns['parents'];offsets=ns['offsets']
  for j,name in enumerate(c['core_bones']):
   i=names.index(name);par=parents[i];pos[i]=pos[par]+offsets[i]@rot[par];rot[i]=rot6(u[j*6:j*6+6])@rot[par]
  i=names.index('upperarm_r');par=parents[i];shoulder=pos[par]+offsets[i]@rot[par];elbow=shoulder+qarm.apply(offsets[names.index('lowerarm_r')]);v=ns['unit'](u[75:78]-elbow)
  fore=R.align_vectors([v],[qhand.apply(axis)])[0]*qhand
  relative=R.from_matrix(mirror@(qarm.inv()*fore).as_matrix()@mirror)
  b=row['raw'];qa=R.from_quat(b['upperarm_r']['future']['q']);qf=R.from_quat(b['lowerarm_r']['future']['q']);err=np.degrees((relative.inv()*(qa.inv()*qf)).magnitude())
  out.append(dict(tick=row['tick'],error=float(err),q=relative.as_quat().tolist(),axis=(mirror@qarm.inv().apply(v)).tolist()))
 twist=0
 for a,b in zip(out,out[1:]):twist+=np.degrees((R.from_quat(b['q'])*R.from_quat(a['q']).inv()).as_rotvec()@a['axis'])
 print(mode,'raw NN reconstructed forearm twist189-229',round(twist,2),'maxerror vs final',max(x['error'] for x in out));print([(x['tick'],round(x['error'],4)) for x in out[:7]])
 report[mode]=dict(raw_forearm_twist=twist,rows=out)
(p/'arm_revolution_raw_report.json').write_text(json.dumps(report,indent=2))
