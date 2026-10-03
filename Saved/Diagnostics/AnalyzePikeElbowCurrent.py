import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/Knee202')
def unit(v):return v/max(np.linalg.norm(v),1e-12)
def sample(row,kind='raw'):
 b={n:row['raw'][n]['future'] for n in ('upperarm_r','lowerarm_r','hand_r','spine_05')} if kind=='raw' else row['meshes'][kind]
 ref=b['spine_05'];inv=R.from_quat(ref['q']).inv()
 s,e,h=[inv.apply(np.array(b[n]['p'])-ref['p']) for n in ('upperarm_r','lowerarm_r','hand_r')]
 axis=unit(h-s);proj=e-s-axis*np.dot(e-s,axis)
 return dict(axis=axis,pole=unit(proj),radius=np.linalg.norm(proj),elbow=e,shoulder=s,hand=h)
def turn(a,b):
 x,y=a['axis'],b['axis'];v=a['pole'];c=np.dot(x,y)
 carried=unit(v-(x+y)*np.dot(v,y)/max(1+c,1e-8))
 return float(np.degrees(np.arctan2(np.dot(y,np.cross(carried,b['pole'])),np.dot(carried,b['pole']))))
for mode in ('baseline','no_inertia','no_return','exit_no_inertia'):
 f=p/('pike_elbow_'+mode+'.json')
 if not f.exists():continue
 d=json.loads(f.read_text());rows=d['rows'];print(mode,d['reason'],len(rows))
 for kind in ('raw',*rows[-1]['meshes'].keys()):
  for lo,hi in ((151,171),(171,215),(261,305)):
   selected=[r for r in rows if lo-1<=r['tick']<=hi];pairs=[]
   for a,b in zip(selected,selected[1:]):
    try:aa,bb=sample(a,kind),sample(b,kind)
    except KeyError:continue
    pairs.append(dict(tick=b['tick'],turn=turn(aa,bb),radius=float(bb['radius'])))
   if pairs:
    print(kind,lo,hi,'sum',round(sum(x['turn'] for x in pairs),2),'abs',round(sum(abs(x['turn']) for x in pairs),2),'largest',sorted(pairs,key=lambda x:abs(x['turn']),reverse=True)[:3])
   if kind=='raw' and lo==171:(p/('pike_elbow_'+mode+'_poles.json')).write_text(json.dumps(pairs,indent=2))
