import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/Knee202')
tags=['elbow365_before','elbow365_fixed'];data={t:{r['tick']:r for r in json.loads((p/(t+'.json')).read_text())['rows']} for t in tags}
def local(row,b,physical=False):
 bones=row['meshes']['PhysicalMesh'] if physical else {n:r['presented'] for n,r in row['raw'].items()}
 s=bones['spine_05'];return R.from_quat(s['q']).inv().apply(np.array(bones[b]['p'])-s['p'])
for tag,rows in data.items():
 for row in rows.values():
  for v in row['raw'].values():
   for k in ['future','presented']:assert np.isfinite(v[k]['p']+v[k]['q']).all()
 print(tag)
 for t in range(360,371):
  row=rows[t];l=local(row,'lowerarm_l');s=local(row,'upperarm_l');h=local(row,'hand_l')
  print(t,'elbow_local',np.round(l,3),'step',round(np.linalg.norm(l-local(rows[t-1],'lowerarm_l')),3),'forearm',round(np.linalg.norm(h-l),3),'physical',np.round(local(row,'lowerarm_l',True),3))
a,b=[data[t] for t in tags]
print('max pre-exit NN position difference',max(np.linalg.norm(np.array(a[t]['raw'][n]['presented']['p'])-b[t]['raw'][n]['presented']['p']) for t in a if 300<=t<=362 for n in a[t]['raw']))
