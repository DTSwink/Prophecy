from pathlib import Path
import sys, json
import torch
torch.set_num_threads(1)
base=Path(__file__).resolve().parent
sys.path.insert(0,str(base/'ReferenceSources/parry/training/slashes2/ParryAndDodge'))
from frozen_parry_collision import confirmed_pair_contacts
g=json.loads((base/'Models/parry_colliders.json').read_text())
ref=json.loads((base/'Models/parry_contact_reference.json').read_text())
frames=ref['frames'];n=len(g['colliders'])
t=lambda a:torch.tensor(a,dtype=torch.float32)
centers=t([f['centers'] for f in frames]).reshape(-1,n,3)
axes=t([f['axes'] for f in frames]).reshape(-1,n,3,3)
attack_c=t([f['attacker_center'] for f in frames]);attack_r=t([f['attacker_axes'] for f in frames]).reshape(-1,3,3)
half=t([v['half'] for v in g['colliders']]);offset=t([v['center_offset'] for v in g['colliders']])
count=len(frames)-1
with torch.inference_mode():
    result=confirmed_pair_contacts(centers[:-1],axes[:-1],centers[1:],axes[1:],half.expand(count,-1,-1),offset.expand(count,-1,-1),
        attack_c[:-1],attack_r[:-1],attack_c[1:],attack_r[1:],t(ref['attacker_half']).expand(count,-1),torch.zeros(count,3))
rows=[]
for f in range(count):
    for i in range(n):
        if not result.possible[f,i]:continue
        rows.append(dict(frame=f+1,collider=g['colliders'][i]['name'],fraction=float(result.time[f,i]),
            gap=float(result.actual_gap[f,i]),confirmed=bool(result.confirmed[f,i]),resolved=bool(result.resolved[f,i]),iterations=int(result.iterations[f,i])))
(base/'Models/parry_contact_cpu_diagnostic.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
