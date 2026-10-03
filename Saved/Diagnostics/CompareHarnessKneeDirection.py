import json,pathlib,sys,numpy as np
p=pathlib.Path('Saved/Diagnostics')
def u(v):return v/max(np.linalg.norm(v),1e-12)
for tag in sys.argv[1:]:
 rows=json.loads((p/(tag+'-capture.json')).read_text(encoding='utf-8'))['rows'];ex=-100;last=None;vals={'l':[],'r':[]}
 for r in rows:
  if r['attack']=='None' and last not in (None,'None'):ex=r['clock']
  last=r['attack']
  if r['attack']!='None' or not 0<=r['clock']-ex<30:continue
  for side in vals:
   b=r['targets'];h,k,f,t=[np.array(b[n+'_'+side]['target']['p']) for n in ('thigh','calf','foot','ball')]
   axis=u(f-h);pole=u(k-h-axis*((k-h)@axis));fw=u((t-f)*[1,1,0]);front=u(fw-axis*(fw@axis));ang=float(np.degrees(np.arctan2(axis@np.cross(front,pole),front@pole)))
   vals[side].append((r['clock'],r['clock']-ex,ang,f[2]-h[2]))
 print(tag)
 for side,items in vals.items():
  a=[abs(x[2]) for x in items if x[3]<-20]
  print(side,'foot at least20cm below hip: mean/max angle from projected forward',np.mean(a),max(a),'>90 count',sum(x>90 for x in a),'/',len(a))
  print('first return',[(x[0],round(x[2],1)) for x in items[:30:2]])
