import json,sys,re,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
def index(path):
    d=json.loads(Path(path).read_text());out={};episode=0;was=False
    for row in d['rows']:
        if row['agent']!='BP_ProphecyManualPoseAgent_C_1':continue
        attacking='ATTACKING' in row['state']
        if attacking and not was:episode+=1
        was=attacking
        if attacking:
            frame=int(re.search(r', (\d+)\)$',row['attack'])[1]);out[(episode,frame)]=row
    return out
a=index(sys.argv[1]);b=index(sys.argv[2]);pos={};rot={};samples=0
for key in a.keys() & b.keys():
    samples+=1
    for name,aa in a[key]['bones'].items():
        bb=b[key]['bones'][name]
        dp=float(np.linalg.norm(np.array(aa[0][:3])-bb[0][:3]));dr=float(np.rad2deg((R.from_quat(aa[0][3:]).inv()*R.from_quat(bb[0][3:])).magnitude()))
        pos[name]=max(pos.get(name,0),dp);rot[name]=max(rot.get(name,0),dr)
out={'matched_attack_samples':samples,'max_future_position_delta_cm':pos,'max_future_rotation_delta_deg':rot}
print(json.dumps(out,indent=2));Path(sys.argv[2]).with_suffix('.comparison.json').write_text(json.dumps(out,indent=2))
