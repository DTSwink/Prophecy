import json,math,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics/Knee202')
base=json.loads((p/'arm_body_first_attack.json').read_text())['rows']
new=json.loads((p/'arm_cone_default.json').read_text())['rows']
b={r['tick']:r for r in base};n={r['tick']:r for r in new}
def angle(r,side):
 m=r['meshes']['PhysicalMesh'];v=lambda k:np.array(m[k]['p'])
 inward=v('upperarm_r')-v('upperarm_l');inward[2]=0;inward/=np.linalg.norm(inward)
 if side=='r':inward=-inward
 d=v('lowerarm_'+side)-v('upperarm_'+side);d/=np.linalg.norm(d)
 return math.degrees(math.acos(float(np.clip(d@inward,-1,1))))
prefix=max(float(np.linalg.norm(np.array(b[t]['meshes']['PhysicalMesh'][k]['p'])-np.array(n[t]['meshes']['PhysicalMesh'][k]['p']))) for t in n if t in b and 5<=t<183 for k in ('upperarm_l','upperarm_r','lowerarm_l','lowerarm_r'))
print('Pre-recovery maximum position difference cm:',prefix)
for t in (183,190,200,205,210,215,220,225,230,235,240,250):
 if t in n and t in b:print(t,{s:[round(angle(b[t],s),3),round(angle(n[t],s),3)] for s in ('l','r')})
for s in ('l','r'):
 ticks=[t for t in n if t in b and 183<=t<=230]
 print(s,'minimum angle baseline/enabled:',min(angle(b[t],s) for t in ticks),min(angle(n[t],s) for t in ticks))
