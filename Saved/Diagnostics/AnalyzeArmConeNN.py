import json,math,numpy as np
from pathlib import Path
p=Path('Saved/Diagnostics/Knee202')
b={r['tick']:r for r in json.loads((p/'arm_cone_million_after.json').read_text())['rows']}
n={r['tick']:r for r in json.loads((p/'arm_cone_nn.json').read_text())['rows']}
def angle(r,source,side='r'):
 def v(k):return np.array(r['meshes']['PhysicalMesh'][k]['p'] if source=='physical' else r['raw'][k][source]['p'])
 i=v('upperarm_r')-v('upperarm_l');i[2]=0;i/=np.linalg.norm(i)
 if side=='r':i=-i
 d=v('lowerarm_'+side)-v('upperarm_'+side);d/=np.linalg.norm(d)
 return math.degrees(math.acos(float(np.clip(i@d,-1,1))))
for t in (181,183,185,190,195,200,205,210,215,220,230,250):
 if t in n and t in b:print(t,'oldNN/newNN/newPhysical',*[round(angle(r,s),3) for r,s in ((b[t],'presented'),(n[t],'presented'),(n[t],'physical'))])
for s in ('future','presented','physical'):
 for side in ('l','r'):
  vals=[(angle(r,s,side),t) for t,r in n.items() if 183<=t<=230]
  print(s,side,'minimum angle/tick',min(vals))
print('pre-exit NN max difference',max(float(np.linalg.norm(np.array(b[t]['raw'][k]['future']['p'])-np.array(n[t]['raw'][k]['future']['p']))) for t in n if t in b and 5<=t<183 for k in ('upperarm_l','upperarm_r','lowerarm_l','lowerarm_r','hand_l','hand_r')))
