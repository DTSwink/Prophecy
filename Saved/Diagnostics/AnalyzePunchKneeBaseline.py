import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics');data=json.loads((p/'PunchKneeBaseline-live.json').read_text(encoding='utf-8'));rows=data['rows']
def u(x):return x/max(np.linalg.norm(x),1e-12)
def yaw(v):return float(np.degrees(np.arctan2(v[1],v[0])))
def wrap(x):return (x+180)%360-180
def measure(b,s):
 h,k,f,t=[np.array(b[n+'_'+s]['p']) for n in ('thigh','calf','foot','ball')]
 axis=u(f-h);upper=k-h;rad=upper-axis*(upper@axis);foot=t-f
 return dict(foot=yaw(foot),knee=yaw(upper),pole=yaw(rad),radius=float(np.linalg.norm(rad)),knee_flat=float(np.linalg.norm(upper[:2])),relative=wrap(yaw(upper)-yaw(foot)),pole_relative=wrap(yaw(rad)-yaw(foot)))
print('capture',data['reason'],len(rows),'ticks',rows[0]['tick'],rows[-1]['tick'],'meshes',list(rows[0]['meshes']))
out=[]
for i in range(1,len(rows)):
 if rows[i-1]['attack']=='None' or rows[i]['attack']!='None':continue
 attack=rows[i-1]['attack'];side='r' if 'kickl' in attack.lower() else 'l'
 print('EXIT',rows[i]['tick'],attack,'support',side)
 for kind in ['targets']+list(rows[i]['meshes']):
  if kind=='targets':get=lambda r:r['targets']
  else:get=lambda r:r['meshes'][kind]
  if 'calf_'+side not in get(rows[i]):continue
  start=measure(get(rows[i-1]),side)
  values=[]
  for r in rows[i:min(len(rows),i+36)]:
   if r['attack']!='None':break
   m=measure(get(r),side);m.update(tick=r['tick'],after=r['tick']-rows[i]['tick'],foot_turn=wrap(m['foot']-start['foot']),knee_turn=wrap(m['knee']-start['knee']),pole_turn=wrap(m['pole']-start['pole']))
   values.append(m)
  print(kind,[(m['tick'],round(m['foot_turn'],2),round(m['knee_turn'],2),round(m['relative'],2),round(m['radius'],2),round(m['knee_flat'],2)) for m in values[::2]])
  out.append(dict(exit=rows[i]['tick'],attack=attack,side=side,kind=kind,start=start,rows=values))
(p/'PunchKneeBaseline-analysis.json').write_text(json.dumps(out,indent=2),encoding='utf-8')

