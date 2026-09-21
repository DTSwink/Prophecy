import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation
root=pathlib.Path(__file__).parent
def load(name):
    return {round(r['time']*60):r for r in map(json.loads,(root/name/'pipeline.jsonl').read_text().splitlines()) if r['actor'].endswith('_C_1')}
b=load('PelvisHitch-20260920-193832');a=load('PelvisHitch-20260920-194230')
def rot(v):
    v=np.array(v);x=v[:3]/np.linalg.norm(v[:3]);y=v[3:]-x*np.dot(x,v[3:]);y/=np.linalg.norm(y)
    return np.array([x,y,np.cross(x,y)])
def angle(x,y):return float(np.degrees(Rotation.from_matrix(rot(x)@rot(y).T).magnitude()))
out=[]
for t,r in b.items():
    if not 149<=t<=193:continue
    current=np.array(r['lower_input'][:41]);pred=current+np.array(r['lower_delta'][:41]);pub=np.array(r['published_lower'])
    row={'tick':t,'legs':{}}
    for leg,o in [('left',18),('right',34)]:
        row['legs'][leg]={'raw_step_deg':angle(current[o:o+6],pred[o:o+6]),'published_step_deg':angle(current[o:o+6],pub[o:o+6]),
            'correction_deg':angle(pred[o:o+6],pub[o:o+6]),'input_difference_norm':float(np.linalg.norm(r['lower_input'][o+76:o+82]))}
    out.append(row)
    print(t,[(k,{n:round(v,3) for n,v in d.items()}) for k,d in row['legs'].items()])
(root/'PelvisHitchInputs/thighs.json').write_text(json.dumps(out,indent=2))
print('175 input difference consistency')
r=b[175];x=np.array(r['lower_input']);scale=(1/15)
for o in (18,34):print(o,'derived',((x[o:o+6]-x[o+41:o+47])/scale).tolist(),'actual',x[o+76:o+82].tolist())
