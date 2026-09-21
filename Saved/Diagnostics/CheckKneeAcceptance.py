import sys,json,pathlib,math,numpy as np
from ReplayTemperedLeg import points,unit
def stats(v):return dict(max=float(max(v,default=0)),p95=float(np.percentile(v,95)) if v else 0)
for arg in sys.argv[1:]:
 p=pathlib.Path(arg);rs=[json.loads(l) for l in (p/'pipeline.jsonl').open()];out={}
 for leg in (0,1):
  rows=[]
  for r in rs:
   if r['actor']!='BP_ProphecyManualPoseAgent_C_1' or r['attack'] or r['time']<1:continue
   h,k,a,t=points(np.array(r['published_lower']),leg);axis=unit(a-h);u=k-h;side=np.cross([0,0,1],unit((t-a)*[1,1,0]));pole=u-axis*np.dot(u,axis)
   rows.append(dict(time=r['time'],distance_cm=float(np.linalg.norm(a-h)*100),side_cm=float(np.dot(u,side)*100),hinge_sign=float(np.dot(unit(pole),unit(np.cross(axis,side)))),radius_cm=float(np.linalg.norm(pole)*100),axis_side=float(abs(np.dot(axis,side)))))
  stable=[r for r in rows if r['radius_cm']>3 and r['axis_side']<.95]
  out[str(leg)]=dict(samples=len(rows),min_reach_cm=min((r['distance_cm'] for r in rows),default=None),side_cm=stats([abs(r['side_cm']) for r in rows]),backward=sum(r['hinge_sign']<0 for r in stable),stable_samples=len(stable),worst_side=max(rows,key=lambda r:abs(r['side_cm'])) if rows else None)
 print(p.name,json.dumps(out));(p/'acceptance.json').write_text(json.dumps(out,indent=2))
