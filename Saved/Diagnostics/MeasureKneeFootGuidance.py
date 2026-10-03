import json,pathlib,numpy as np,sys
p=pathlib.Path('Saved/Diagnostics')
def u(v):return v/max(np.linalg.norm(v),1e-12)
for tag in sys.argv[1:]:
 rows=json.loads((p/(tag+'-capture.json')).read_text(encoding='utf-8'))['rows'];angles=[]
 for r in rows:
  if not 145<=r['clock']<=174:continue
  b=r['targets'];h,k,f,t=[np.array(b[n+'_l']['target']['p']) for n in ('thigh','calf','foot','ball')]
  axis=u(f-h);pole=u(k-h-axis*((k-h)@axis));toe=u((t-f)*[1,1,0]);desired=u(toe-axis*(toe@axis))
  ang=np.degrees(np.arctan2(axis@np.cross(desired,pole),desired@pole));angles.append(float(ang))
 print(tag,'first30 pole/foot-heading angle',np.round(angles,1).tolist(),'meanabs',np.mean(np.abs(angles)))
