import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/Knee202')
def unit(x):return x/max(np.linalg.norm(x),1e-12)
def data(r):return {k:v['future'] for k,v in r['raw'].items()}
out={}
for mode in ('damping_before','damping_after'):
 f=p/f'wrist_recoil_{mode}.json'
 if not f.exists():continue
 rows=json.loads(f.read_text())['rows'];lastattack=False;end=None
 for r in rows:
  attack=r['attack']!='None'
  if lastattack and not attack:end=r['tick'];break
  lastattack=attack
 if end is None:raise RuntimeError('No attack end')
 before=data(next(r for r in rows if r['tick']==end-1));side={}
 for name in ('l','r'):
  u,l,h=['upperarm_'+name,'lowerarm_'+name,'hand_'+name];q0=R.from_quat(before[l]['q']);ref=R.from_quat(before['spine_05']['q']).inv()*q0;axislocal=q0.inv().apply(unit(np.array(before[h]['p'])-before[l]['p']));basis=np.array([0,0,1]) if abs(axislocal[2])<.8 else np.array([0,1,0]);radial=unit(basis-axislocal*(basis@axislocal));vals=[];near=0
  for r in rows:
   if not end<=r['tick']<=end+90:continue
   b=data(r);axis=unit(np.array(b[h]['p'])-b[l]['p']);qref=R.from_quat(b['spine_05']['q'])*ref;transport=R.align_vectors([axis],[qref.apply(axislocal)])[0];rr=unit(transport.apply(qref.apply(radial)));actual=R.from_quat(b[l]['q']).apply(radial);actual=unit(actual-axis*(actual@axis));angle=np.arctan2(axis@np.cross(rr,actual),rr@actual);angle=near+(angle-near+np.pi)%(2*np.pi)-np.pi;near=angle;vals.append((r['tick'],float(np.degrees(angle))))
  side[name]=vals;print(mode,name,'range',min(v for _,v in vals),max(v for _,v in vals),'sample',vals[::10])
 out[mode]=dict(end=end,sides=side)
if len(out)==2:
 a={r['tick']:r for r in json.loads((p/'wrist_recoil_damping_before.json').read_text())['rows']};b={r['tick']:r for r in json.loads((p/'wrist_recoil_damping_after.json').read_text())['rows']}
 print('pre-exit pose error',max(np.linalg.norm(np.array(a[t]['raw'][n]['future']['p'])-b[t]['raw'][n]['future']['p']) for t in a if t<out['damping_before']['end'] for n in a[t]['raw']))
(p/'wrist_recoil_damping_analysis.json').write_text(json.dumps(out,indent=2))
