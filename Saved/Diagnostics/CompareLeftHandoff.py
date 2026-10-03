import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics/ArmReach');tags=sys.argv[1:] or ['left_stages','twist_latefix','twist_final']
sets=[]
for tag in tags:
 d=json.loads((p/(tag+'.json')).read_text());assert d['reason']=='Complete';sets.append({r['tick']:r for r in d['rows']})
result={}
for tag,d in zip(tags,sets):
 metrics={}
 for arm in ['l','r']:
  v=[]
  for t in range(122,210):
   q=R.from_quat(d[t]['pose']['upperarm_'+arm]['future']['q']);prev=R.from_quat(d[t-1]['pose']['upperarm_'+arm]['future']['q'])
   v.append((t,float((prev.inv()*q).magnitude()*180/np.pi)))
  metrics[arm]=dict(max_upper_rotation=max(v,key=lambda x:x[1]),around163=[x for x in v if 155<=x[0]<=189 and x[0]%2==1])
 metrics['prefix_to162_position_cm']=max(float(np.linalg.norm(np.array(x['future']['p'])-sets[0][t]['pose'][bone]['future']['p'])) for t,r in d.items() if t<=162 for bone,x in r['pose'].items())
 metrics['prefix_to162_rotation_deg']=max(float((R.from_quat(x['future']['q']).inv()*R.from_quat(sets[0][t]['pose'][bone]['future']['q'])).magnitude()*180/np.pi) for t,r in d.items() if t<=162 for bone,x in r['pose'].items())
 result[tag]=metrics
print(json.dumps(result,indent=2));(p/('compare_left_'+tags[-1]+'.json')).write_text(json.dumps(result,indent=2))
