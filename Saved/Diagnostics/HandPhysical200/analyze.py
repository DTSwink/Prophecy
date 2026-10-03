import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).resolve().parent
d=json.loads((p/'baseline.json').read_text(encoding='utf8'));rows={r['tick']:r for r in d['rows']}
def angle(a,b):return float(np.degrees((R.from_quat(a['q'])*R.from_quat(b['q']).inv()).magnitude()))
out=[]
for t,r in rows.items():
 if t<20:continue
 item=dict(tick=t,attack=r['attack'],mode=r['mode'],bones={})
 for b in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r'):
  body=r['bodies'].get(b);target=r['targets'].get(b)
  if not body or not target:continue
  raw=r['raw'][b]['presented'];phys=r['meshes']['PhysicalMesh'][b]
  x=dict(body_target_deg=angle(body['transform'],target['target']),mesh_target_deg=angle(phys,target['target']),target_raw_deg=angle(target['target'],raw),body_mesh_deg=angle(body['transform'],phys),body_target_cm=float(np.linalg.norm(np.array(body['transform']['p'])-target['target']['p'])))
  for name,poses in r['meshes'].items():
   if name!='PhysicalMesh' and b in poses:x[name+'_target_deg']=angle(poses[b],target['target'])
  item['bones'][b]=x
 out.append(item)
(p/'analysis.json').write_text(json.dumps(out,indent=2),encoding='utf8')
print('reason',d['reason'],'meshes',list(rows[200]['meshes']))
last=None
for r in d['rows']:
 # Attack state contains frame; print changes of family/activity only.
 key=r['attack'].split(',')[:2]
 if key!=last:print('state',r['tick'],r['attack']);last=key
for r in out:
 if r['tick'] in [50,100,140,150,175,180,185,190,195,198,199,200,201,202,205,210,220,240,260]:
  print(r['tick'],r['attack'],' '.join(b+':'+str(round(v['body_target_deg'],3)) for b,v in r['bones'].items()))
print('tick200',json.dumps(next(r for r in out if r['tick']==200),indent=2))
for t in [180,195,200,205,220]:
 print('settings',t,rows[t].get('limits'),rows[t].get('profile'))
