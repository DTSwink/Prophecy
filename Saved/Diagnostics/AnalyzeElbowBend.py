import json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
def norm(v): return v/max(1e-12,np.linalg.norm(v))
def deg(a,b):return float(np.degrees(np.arccos(np.clip(np.dot(norm(a),norm(b)),-1,1))))
for path in sys.argv[1:]:
 d=json.loads(Path(path).read_text());last={};exits={};groups={}
 for r in d['rows']:
  a=r['agent'];old=last.get(a);last[a]=r
  if old and 'ATTACKING' in old['state'] and 'LOCOMOTION' in r['state']:exits[a]=(r['frame'],old['attack'])
  if a not in exits or 'LOCOMOTION' not in r['state']:continue
  f,attack=exits[a]
  if r['frame']-f>90:continue
  b=r['bones'];p=lambda n:np.array(b[n][0][:3]);up=norm(p('neck_01')-p('pelvis'));right=p('upperarm_r')-p('upperarm_l');right=norm(right-up*np.dot(right,up));m=np.stack([np.cross(right,up),right,up]);o=(p('upperarm_l')+p('upperarm_r'))/2
  s,e,h=[m@(p(n)-o) for n in ('upperarm_r','lowerarm_r','hand_r')];ax=norm(h-s);pole=norm(e-s-ax*np.dot(e-s,ax));reach=np.linalg.norm(h-s);l1=np.linalg.norm(e-s);l2=np.linalg.norm(h-e)
  g=groups.setdefault((a,f),{'attack':attack,'rows':[]})
  g['rows'].append({'tick':r['frame']-f,'reach':round(reach,3),'bend':round(deg(s-e,h-e),3),'pole':pole.round(3).tolist(),'s':s.round(2).tolist(),'e':e.round(2).tolist(),'h':h.round(2).tolist(),'lengths':[round(l1,3),round(l2,3)]})
 out=[{'agent':a,'exit':f,**g} for (a,f),g in groups.items()]
 Path(path).with_suffix('.elbows.json').write_text(json.dumps(out,indent=2))
 print(path,d['frames'],d['error'])
 for g in out:
  print(g['agent'],g['exit'],g['attack']);print('reach min',min(x['reach'] for x in g['rows']))
  for x in g['rows'][::6]:print(x)
