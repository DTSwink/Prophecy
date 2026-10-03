import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics');rows=[json.loads(l) for l in (p/'KneeHistoricalSolve.jsonl').read_text(encoding='utf-8').splitlines()]
def unit(v):return v/max(np.linalg.norm(v),1e-12)
def rot(s,o):
 x=unit(s[o:o+3]);y=unit(np.array(s[o+3:o+6])-x*np.dot(x,s[o+3:o+6]));return np.array([x,y,np.cross(x,y)])
def angle(a,b):return float(np.degrees(np.arccos(np.clip(unit(a)@unit(b),-1,1))))
def geo(r,key):
 s=np.array(r[key]);o=r['offset'];hip=s[:3]+np.array(r['hip'])@rot(s,3);u=np.array(r['knee'])@rot(s,o+9);ax=unit(s[o:o+3]-hip);rad=u-ax*(u@ax);pole=unit(rad);toe=unit(r['forward'])@rot(s,o+3);f=unit(toe*[1,1,0]);side=np.cross([0,0,1],f)
 return dict(axis=ax,pole=pole,radius=np.linalg.norm(rad)*100,k=hip+u,yaw=float(np.degrees(np.arctan2(u@side,u@f))),heading=float(np.degrees(np.arctan2(f[1],f[0]))),q=R.from_matrix(rot(s,o+9)))
tr=[json.loads(l) for l in (p/'KneeHistoricalAudit-nn.jsonl').read_text(encoding='utf-8').splitlines()]
actor=json.loads((p/'KneeHistoricalAudit-capture.json').read_text())['rows'][0]['actor'];tr=[r for r in tr if r['actor']==actor]
out=[]
for r in rows:
 n=min(tr,key=lambda n:np.linalg.norm(np.array(n['previous_lower'])-r['previous']))
 err=float(np.linalg.norm(np.array(n['previous_lower'])-r['previous']))
 if err>.001:continue
 a=geo(r,'current');b=geo(r,'historical');prev=geo(r,'previous');o=r['offset'];nn=geo(r,'nn') if 'nn'in r else None
 x=dict(tick=round(n['time']*60),side='l'if o==9 else'r',follow=r['settings'][1],difference=float(np.degrees((a['q']*b['q'].inv()).magnitude())),current=a['yaw'],historical=b['yaw'],prior=prev['yaw'],heading=a['heading'],source=nn['yaw'] if nn else None)
 out.append(x)
(p/'KneeHistoricalSolve-metrics.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print('matched',len(out),'total',len(rows))
for x in out:
 if 145<=x['tick']<=177:print({k:round(v,2) if isinstance(v,float)else v for k,v in x.items()})
