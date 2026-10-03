import json,pathlib,math,collections
import numpy as np
p=pathlib.Path(__file__).resolve().parent
a=json.loads((p/'motion_original.json').read_text(encoding='utf8'))
b=json.loads((p/'motion_native.json').read_text(encoding='utf8'))
assert a['reason']==b['reason']=='Complete',(a['reason'],b['reason'])
assert a['events']==b['events']
assert len(a['rows'])==len(b['rows'])
report={}
for i,(x,y) in enumerate(zip(a['rows'],b['rows'])):
 assert x['frame']==y['frame']
 family=a['events'][i//80]['family']
 r=report.setdefault(family,dict(future_cm=0,future_deg=0,presented_cm=0,presented_deg=0,state_differences=0))
 r['state_differences']+=x['state']!=y['state']
 for field in ('future','presented'):
  X,Y=np.array(x[field]),np.array(y[field])
  pos=np.max(np.linalg.norm(X[:,:3]-Y[:,:3],axis=-1))
  Xq=X[:,3:];Yq=Y[:,3:];Xq/=np.linalg.norm(Xq,axis=-1,keepdims=True);Yq/=np.linalg.norm(Yq,axis=-1,keepdims=True)
  angle=np.max(np.degrees(2*np.arccos(np.clip(np.abs(np.sum(Xq*Yq,axis=-1)),0,1))))
  r[field+'_cm']=max(float(pos),r[field+'_cm']);r[field+'_deg']=max(float(angle),r[field+'_deg'])
(p/'motion-comparison.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
assert len(report)==16
assert all(r['state_differences']==0 and r['future_cm']<.001 and r['presented_cm']<.001 and r['future_deg']<.01 and r['presented_deg']<.01 for r in report.values())
