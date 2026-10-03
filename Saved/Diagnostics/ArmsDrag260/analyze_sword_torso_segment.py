from pathlib import Path
import json,math,sys
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(__file__).parent
for tag in sys.argv[1:]:
 data=json.loads((p/(tag+'.json')).read_text());rows=[]
 for r in data['rows']:
  if not r['player'] or not 191<=r['tick']<=312:continue
  w=r['weapon'];center=(np.array(w['lo'])+w['hi'])/2;axis=int(np.argmax(np.array(w['hi'])-w['lo']))
  ends=[]
  for z in (w['lo'][axis],w['hi'][axis]):
   pt=center.copy();pt[axis]=z;ends.append(R.from_quat(w['actual']['q']).apply(pt*np.array(w.get('actual_scale',w['scale'])))+w['actual']['p'])
  a,b=ends;blade=b-a;length=np.linalg.norm(blade);blade/=length
  pelvis=np.array(r['presented']['pelvis']['p']);spine=np.array(r['presented']['spine_05']['p'])
  pts=pelvis[None,:]+np.linspace(0,1,501)[:,None]*(spine-pelvis);v=pts-a;along=np.clip(v@blade,0,length);dist=np.linalg.norm(v-along[:,None]*blade,axis=1);i=np.argmin(dist)
  rows.append(dict(tick=r['tick'],centreline_clearance_cm=float(dist[i]),sword_along_cm=float(along[i]),torso_fraction=float(i/500)))
 summary=dict(minimum=min((r['centreline_clearance_cm'],r['tick']) for r in rows),samples=[r for r in rows if r['tick'] in (191,200,210,215,216,220,230,240,250,281,301,310,312)])
 (p/(tag+'_torso_segment.json')).write_text(json.dumps(dict(summary=summary,rows=rows),indent=2))
 print(tag,json.dumps(summary))
