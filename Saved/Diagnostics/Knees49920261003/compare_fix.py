import json,numpy as np
from pathlib import Path
p=Path(__file__).parent
a={r['tick']:r for r in json.loads((p/'baseline.json').read_text())['rows']}
b={r['tick']:r for r in json.loads((p/'fixed.json').read_text())['rows']}
def pole(r,kind):
 h,k,f=[np.array(r['bones'][x+'_r'][kind]['p']) for x in ['thigh','calf','foot']]
 axis=f-h;axis/=np.linalg.norm(axis);u=k-h;v=u-axis*(u@axis)
 return v/np.linalg.norm(v)
rows=[]
for t in range(494,521):
 r={'tick':t}
 for label,data in [('before',a),('after',b)]:
  for kind in ['presented','body']:
   r[label+'_'+kind+'_pole_step']=float(np.degrees(np.arccos(np.clip(pole(data[t-1],kind)@pole(data[t],kind),-1,1))))
 rows.append(r)
result={'rows':rows,'future_lower_max_cm_494_520':float(max(np.linalg.norm(np.array(a[t]['bones'][bone]['future']['p'])-b[t]['bones'][bone]['future']['p']) for t in range(494,521) for bone in ['pelvis','thigh_r','calf_r','foot_r']))}
(p/'fix-comparison.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
