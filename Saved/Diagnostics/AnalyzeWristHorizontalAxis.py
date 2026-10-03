import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/Knee202');report={}
for mode in ('axis_before','axis_after'):
 f=p/f'wrist_stop_{mode}.json'
 if not f.exists():continue
 rows=json.loads(f.read_text())['rows'];prevrow=next(r for r in rows if r['tick']==188);b=prevrow['raw'];sp=R.from_quat(b['spine_05']['future']['q']);ref=sp.inv()*R.from_quat(b['hand_r']['future']['q']);axis=sp.inv().apply(np.array(b['neck_01']['future']['p'])-b['spine_05']['future']['p']);axis/=np.linalg.norm(axis);near=0;prev=ref;out=[]
 for r in rows:
  if not 189<=r['tick']<=250:continue
  b=r['raw'];sp=R.from_quat(b['spine_05']['future']['q']);q=sp.inv()*R.from_quat(b['hand_r']['future']['q']);d=(q*ref.inv()).as_quat();a=2*np.arctan2(d[:3]@axis,d[3]);a=near+(a-near+np.pi)%(2*np.pi)-np.pi
  step=float(np.degrees((q*prev.inv()).magnitude()));near=a;prev=q
  sword=R.from_quat(b['spine_05']['presented']['q']).inv()*R.from_quat(r['sword']['sword']['q']);out.append(dict(tick=r['tick'],angle=float(np.degrees(a)),step=step,sword_spine_q=sword.as_quat().tolist()))
 print(mode,[(x['tick'],round(x['angle'],2),round(x['step'],2)) for x in out if x['tick']%2 and x['tick']<=221]);report[mode]=out
if 'axis_after' in report:
 on=[r for r in report['axis_after'] if abs(r['angle'])>=59.9 and r['tick']>193]
 print('near boundary max wrist step',max((x['step'] for x in on),default=0))
(p/'wrist_horizontal_axis_analysis.json').write_text(json.dumps(report,indent=2))
