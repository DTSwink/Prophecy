import json
from pathlib import Path
import numpy as np

p=Path(__file__).parent
def read(name):
 d=json.loads((p/(name+'.json')).read_text())
 assert d['reason']=='Complete',d['reason']
 return {r['tick']:r for r in d['rows']}
a=read('baseline');b=read('pelvis_off_496')
def points(row,kind):
 return [np.array(row['bones'][bone+'_r'][kind]['p']) for bone in ('thigh','calf','foot')]
def geometry(points):
 h,k,f=points;axis=f-h;axis/=np.linalg.norm(axis)
 u=k-h;radial=u-axis*(u@axis);radius=np.linalg.norm(radial)
 return radial/radius,radius
def angle(x,y):return float(np.degrees(np.arccos(np.clip(x@y,-1,1))))
rows=[];previous=None
for t in range(495,503):
 r=a[t];end=t-(t%2);alpha=r['alpha']
 raw=[x*(1-alpha)+y*alpha for x,y in zip(points(a[end-2],'future'),points(a[end],'future'))]
 pole,radius=geometry(raw);visible,visible_radius=geometry(points(r,'presented'))
 variant,variant_radius=geometry(points(b[t],'presented'))
 row=dict(tick=t,alpha=alpha,raw_radius_cm=float(radius),visible_radius_cm=float(visible_radius),
          variant_radius_cm=float(variant_radius),variant_raw_position_error_cm=float(max(np.linalg.norm(x-y) for x,y in zip(raw,points(b[t],'presented')))))
 if previous:
  row.update(raw_pole_step_deg=angle(previous[0],pole),visible_pole_step_deg=angle(previous[1],visible),variant_pole_step_deg=angle(previous[2],variant))
 rows.append(row);previous=pole,visible,variant
result=dict(rows=rows,
 prefix_presented_max_cm=float(max(np.linalg.norm(np.array(a[t]['bones'][bone]['presented']['p'])-b[t]['bones'][bone]['presented']['p']) for t in a if t<=496 for bone in a[t]['bones'])),
 future_max_cm_494_502=float(max(np.linalg.norm(np.array(a[t]['bones'][bone]['future']['p'])-b[t]['bones'][bone]['future']['p']) for t in range(494,503) for bone in a[t]['bones'])))
(p/'analysis.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
