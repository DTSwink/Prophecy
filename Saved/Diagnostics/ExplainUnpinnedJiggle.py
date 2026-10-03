import json,pathlib,numpy as np,math
from ReplayTemperedLeg import clean,points
p=pathlib.Path(__file__).parent
rows=json.loads((p/'CalfAnkleConnection-pin-jiggle-current.json').read_text())['rows']
actor=rows[0]['actor']
nn=[x for x in map(json.loads,(p/'FootVibration-nn-pin-jiggle-current.jsonl').read_text().splitlines()) if x['actor']==actor and not x['attack']]
def angle(s):
 h,k,f,_=points(s);u=k-h;v=f-k
 return math.degrees(math.acos(np.clip(np.dot(u,v)/np.linalg.norm(u)/np.linalg.norm(v),-1,1)))
out=[]
for x in nn:
 if not 4.25<=x['time']<=4.45:continue
 raw=clean(np.array(x['lower_input'][:41])+x['lower_delta'][:41]);pub=np.array(x['published_lower'])
 h,k,f,_=points(raw);H,K,F,_=points(pub);u=np.linalg.norm(k-h);l=np.linalg.norm(F-K)
 projected=k+(f-k)*l/np.linalg.norm(f-k)
 rec=dict(frame=round(x['time']*60),raw_angle=angle(raw),published_angle=angle(pub),raw_distance=np.linalg.norm(f-h)*100,
   reach=(u+l)*100,returned_calf=l*100,raw_calf=np.linalg.norm(f-k)*100,
   preserve_nn_bend_foot_change=np.linalg.norm(projected-F)*100,
   selected=x['lower_delta'][41:],tempering=x.get('tempering'))
 out.append(rec);print({k:round(v,4)if isinstance(v,float)else v for k,v in rec.items()})
(p/'UnpinnedJiggle-analysis.json').write_text(json.dumps(out,indent=2))
