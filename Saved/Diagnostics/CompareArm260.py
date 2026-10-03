import json,numpy as np,sys
from pathlib import Path
p=Path('Saved/Diagnostics/ArmReach')
tags=sys.argv[1:] or ['instability260','route_latefix','body_route']
data=[]
for tag in tags:
 d=json.loads((p/(tag+'.json')).read_text());assert d['reason']=='Complete';data.append({r['tick']:r for r in d['rows']})
result={}
for tag,d in zip(tags,data):
 vals={}
 for kind in ['future','presented']:
  points=np.array([d[t]['pose']['hand_r'][kind]['p'] for t in range(239,270)])
  steps=np.linalg.norm(np.diff(points,axis=0),axis=1)
  vals[kind]=dict(max_step_cm=float(max(steps)),max_step_tick=int(np.argmax(steps)+240),steps={t:round(float(steps[t-240]),5) for t in [249,251,253,255,257,259,261,263,265,267,269]})
 vals['prefix_to_252_cm']=max(float(np.linalg.norm(np.array(v['future']['p'])-data[0][t]['pose'][n]['future']['p'])) for t in d if t<=252 for n,v in d[t]['pose'].items())
 result[tag]=vals
print(json.dumps(result,indent=2));(p/('compare260_'+tags[-1]+'.json')).write_text(json.dumps(result,indent=2))
