import json,pathlib,numpy as np,sys
from scipy.spatial.transform import Rotation
p=pathlib.Path('Saved/Diagnostics')
def load(tag):return {r['clock']:r for r in json.loads((p/(tag+'-capture.json')).read_text(encoding='utf-8'))['rows']}
def unit(v):return v/max(np.linalg.norm(v),1e-12)
def angle(a,b):return float(np.degrees(np.arccos(np.clip(np.dot(unit(a),unit(b)),-1,1))))
def geom(r,side,kind):
 b={k:v[kind] for k,v in r['targets'].items()} if kind!='PhysicalMesh' else r['meshes'][kind]
 h,k,f=[np.array(b[n+'_'+side]['p']) for n in ('thigh','calf','foot')];axis=unit(f-h);pole=unit(k-h-axis*np.dot(k-h,axis))
 return dict(h=h,k=k,f=f,axis=axis,pole=pole,bend=angle(k-h,f-k),q=b['thigh_'+side]['q'])
def step(a,b,side,kind):
 x=geom(a,side,kind);y=geom(b,side,kind);pole=x['pole']-(x['axis']+y['axis'])*np.dot(x['pole'],y['axis'])/max(1e-9,1+np.dot(x['axis'],y['axis']))
 return dict(pole_turn=angle(pole,y['pole']),knee_step=float(np.linalg.norm(y['k']-x['k'])),bend=y['bend'],thigh_turn=float(np.degrees((Rotation.from_quat(y['q'])*Rotation.from_quat(x['q']).inv()).magnitude())))
if __name__=='__main__':
 a=load('Knee1089');tag=sys.argv[1] if len(sys.argv)>1 else 'Knee1089Fixed';b=load(tag);err=0
 for n in sorted(a.keys()&b.keys()):
  if n>1088:break
  for bone in a[n]['targets']:
   for kind in ('previous','future','target'):
    for component in ('p','q'):
     err=max(err,float(np.max(np.abs(np.array(a[n]['targets'][bone][kind][component])-b[n]['targets'][bone][kind][component]))))
 print('identical prefix error',err);assert err==0
 result={'prefix_error':err,'rows':[]}
 for n in range(1087,1095):
  for kind in ('target','future','PhysicalMesh'):
   x=step(a[n-1],a[n],'l',kind);y=step(b[n-1],b[n],'l',kind)
   result['rows'].append(dict(tick=n,kind=kind,before=x,after=y))
   if kind=='target':print(n,'pole %.3f -> %.3f'%(x['pole_turn'],y['pole_turn']),'knee cm %.3f -> %.3f'%(x['knee_step'],y['knee_step']),'thigh %.3f -> %.3f'%(x['thigh_turn'],y['thigh_turn']))
 (p/(tag+'-comparison.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
