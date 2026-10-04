import pathlib,json,re
import numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).parent
def rows(name):return {r['tick']:r for r in json.loads((p/(name+'.json')).read_text())['rows']}
base=rows('baseline');raw=rows('no_return')
def local(row,b,parent):
 q=row['bones'][b]['future']['q'];qp=row['bones'][parent]['future']['q']
 return R.from_quat(qp).inv()*R.from_quat(q)
text=pathlib.Path('Source/GameAnimationSample3/Private/ProphecyFKReturnData.h').read_text()
bones=re.findall(r'\{TEXT\("(.*?)"\), TEXT\("(.*?)"\), (\d), \{(.*?)\}, \{(.*?)\}\}',text)
weights=[0,.19,1,.63,1,1,1,0]
elapsed=2/60;duration=.3;x=elapsed/duration
blend=x**3*(10+x*(-15+6*x));nn=(elapsed/(duration*.65))**2
out=[]
for name,parent,g,q,pos in bones:
 g=int(g);a=local(base[130],name,parent);z=local(base[132],name,parent)
 idle=R.from_quat([float(s.removesuffix('f')) for s in q.split(',')])
 velocity=(a.inv()*z).as_rotvec()*30
 m=elapsed*(1-x)**3*np.exp(-elapsed/(duration*(.025+.45*weights[g]))) if weights[g] else 0
 lab=z*R.from_rotvec((z.inv()*idle).as_rotvec()*blend)*R.from_rotvec(velocity*m)
 target=local(raw[134],name,parent)
 expected=lab*R.from_rotvec((lab.inv()*target).as_rotvec()*nn)
 actual=local(base[134],name,parent)
 out.append(dict(bone=name,inertia=weights[g],outgoing_deg_per_tick=float(np.linalg.norm(velocity)*180/np.pi/60),momentum_seconds=float(m),first_interval_retained_fraction=float(m/elapsed),error_degrees=float(np.rad2deg((expected.inv()*actual).magnitude()))))
result=dict(first_return_elapsed=elapsed,blend=blend,nn_weight=nn,bones=out,
 upperarm_momentum=[dict(ticks=t,seconds=float((t/60)*(1-t/60/duration)**3*np.exp(-(t/60)/(duration*.475)))) for t in (0,2,3,4,6,8,10)],
 max_rotation_error_degrees=max(r['error_degrees'] for r in out))
(p/'curve-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
