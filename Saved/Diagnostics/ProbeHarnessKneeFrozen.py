import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics')
def unit(v):return v/max(np.linalg.norm(v),1e-12)
def rot(s,o):
 a=unit(s[o:o+3]);b=unit(s[o+3:o+6]-a*(s[o+3:o+6]@a));return np.array([a,b,np.cross(a,b)])
def blend(a,b,t):
 a=unit(a);b=unit(b);axis=np.cross(a,b);c=np.clip(a@b,-1,1);sn=np.linalg.norm(axis)
 if sn<1e-9:
  if c>0:return a
  axis=unit(np.cross(a,[1,0,0] if abs(a[0])<.9 else [0,1,0]))
 else:axis/=sn
 return R.from_rotvec(axis*np.arctan2(sn,c)*t).apply(a)
def angle(a,b):return float(np.degrees(np.arccos(np.clip(unit(a)@unit(b),-1,1))))
rows=[json.loads(l) for l in (p/'KneeHistoricalSolve.jsonl').read_text(encoding='utf-8').splitlines()]
results=[]
for i,r in enumerate(rows):
 o=r['offset'];ko=np.array(r['knee']);ho=np.array(r['hip']);gp=np.array(r['pole']);target=np.array(r['current']);prev=np.array(r['previous']);nn=np.array(r['nn']);follow=r['settings'][1]
 h=target[:3]+ho@rot(target,3);axis=unit(target[o:o+3]-h);up=ko@rot(target,o+9);along=up@axis;radius=np.linalg.norm(up-axis*along);oldpole=unit(up-axis*along)
 for mode in [1,2]:
  def local(s):
   sh=s[:3]+ho@rot(s,3);sa=unit(s[o:o+3]-sh);su=ko@rot(s,o+9);rad=su-sa*(su@sa);auth=gp@rot(s,o+9);auth=unit(auth-sa*(auth@sa));pole=unit(rad) if np.linalg.norm(rad)>1e-10 else auth
   threshold=.005*(np.linalg.norm(ko)+r['calf']);trust=np.clip((np.linalg.norm(rad)-threshold)/threshold,0,1);trust=trust*trust*(3-2*trust)
   if mode==2:pole=blend(auth,pole,trust)
   return pole@rot(s,o+3).T
  mixed=blend(local(prev),local(nn),follow);world=mixed@rot(target,o+3);proj=world-axis*(world@axis);length=np.linalg.norm(proj);trust=np.clip(length/.05,0,1);trust=trust*trust*(3-2*trust);newpole=blend(oldpole,unit(proj),trust)
  knee=h+axis*along+newpole*radius
  results.append(dict(record=i,side='l' if o==9 else 'r',mode=mode,follow=follow,radius_cm=radius*100,pole_difference=angle(oldpole,newpole),knee_change_cm=float(np.linalg.norm(knee-h-up)*100),projection_length=float(length),calf_error_cm=float(abs(np.linalg.norm(target[o:o+3]-knee)-np.linalg.norm(target[o:o+3]-h-up))*100)))
assert all(np.isfinite(list(r.values())[4:]).all() for r in results)
assert max(r['calf_error_cm'] for r in results)<1e-8
(p/'HarnessKneeFrozen-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
for mode in [1,2]:
 for side in ['l','r']:
  a=[x for x in results if x['mode']==mode and x['side']==side]
  print(mode,side,'max pole difference',max(x['pole_difference'] for x in a),'max knee change cm',max(x['knee_change_cm'] for x in a),'min projection length',min(x['projection_length'] for x in a))
print('All frozen endpoint/segment-length constraints retained; not a rollout validation')
