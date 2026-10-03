import json,pathlib,sys,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics');tag=sys.argv[1] if len(sys.argv)>1 else 'KneeHistoricalBaseline'
d=json.loads((p/(tag+'-capture.json')).read_text(encoding='utf-8'));rows=d['rows'];out=[]
def unit(v):return v/max(np.linalg.norm(v),1e-10)
def angle(a,b):return float(np.degrees(np.arccos(np.clip(unit(a)@unit(b),-1,1))))
def geo(r,s,kind):
 b={n:x[kind] for n,x in r['targets'].items()} if kind in ('target','future') else r['meshes'][kind]
 h,k,f,t=[np.array(b[n+'_'+s]['p']) for n in ('thigh','calf','foot','ball')]
 axis=unit(f-h);upper=k-h;rad=upper-axis*(upper@axis);pole=unit(rad);toe=unit(t-f);forward=unit(toe*np.array([1,1,0]));side=np.cross([0,0,1],forward)
 return dict(axis=axis,pole=pole,k=k,f=f,q=b['thigh_'+s]['q'],radius=float(np.linalg.norm(rad)),bend=angle(upper,f-k),yaw=float(np.degrees(np.arctan2(upper@side,upper@forward))),footh=float(np.degrees(np.arctan2(toe[1],toe[0]))))
lastattack=None;exitframe=-1000
for i,r in enumerate(rows):
 if r['attack']!='None':lastattack=r['attack']
 elif i and rows[i-1]['attack']!='None':exitframe=r['clock'];print('EXIT',exitframe,lastattack)
 for s in ('l','r'):
  for kind in ('target','future','PhysicalMesh'):
   g=geo(r,s,kind);x=dict(tick=r['clock'],side=s,kind=kind,attack=r['attack'],last=lastattack,after=r['clock']-exitframe,**{k:g[k] for k in ('radius','bend','yaw','footh')})
   if i:
    b=geo(rows[i-1],s,kind);carried=b['pole']-(b['axis']+g['axis'])*(b['pole']@g['axis'])/max(1+b['axis']@g['axis'],1e-9)
    x.update(poleturn=angle(carried,g['pole']),kneestep=float(np.linalg.norm(g['k']-b['k'])),footstep=float(np.linalg.norm(g['f']-b['f'])),thighturn=float(np.degrees((R.from_quat(g['q'])*R.from_quat(b['q']).inv()).magnitude())))
   out.append(x)
(p/(tag+'-metrics.json')).write_text(json.dumps(out),encoding='utf-8')
print(d['reason'],len(rows),set(r['mode'] for r in rows))
for key in ('poleturn','yaw','thighturn'):
 arr=[x for x in out if x['kind']=='target' and 0<=x['after']<=100 and x['attack']=='None' and key in x]
 print('TOP',key,[(x['tick'],x['side'],round(x[key],2),round(x['radius'],2),x['after']) for x in sorted(arr,key=lambda x:abs(x[key]),reverse=True)[:15]])
