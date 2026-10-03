import json,sys,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
path=Path(sys.argv[1]);data=json.loads(path.read_text())
c=json.loads(Path('Content/locomotion/NN/prophecy_slash_native.json').read_text(encoding='utf-8'))
result={}
for row in data['rows']:
    state=row['state']
    if not any(m in state for m in ('ATTACKING','PARRYING','DODGING')):continue
    for i,side in enumerate(('l','r')):
        axis=np.array(c['full_geometry']['local_offsets'][c['full_limbs'][i]['end']])*[1,-1,1];axis/=np.linalg.norm(axis)
        f=np.array(row['bones']['lowerarm_'+side][0]);h=np.array(row['bones']['hand_'+side][0])
        fq,hq=R.from_quat(f[3:]),R.from_quat(h[3:]);aim=h[:3]-f[:3];aim/=np.linalg.norm(aim)
        start=hq.apply(axis);dot=np.dot(start,aim);cross=np.cross(start,aim)
        assert dot>-.999999,'Unexpected antiparallel test pose'
        q=np.r_[cross,1+dot];expected=R.from_quat(q/np.linalg.norm(q))*hq
        error=float(np.degrees((fq.inv()*expected).magnitude()))
        key=state+'/'+side;r=result.setdefault(key,{'samples':0,'max_roll_mismatch_deg':0})
        r['samples']+=1;r['max_roll_mismatch_deg']=max(r['max_roll_mismatch_deg'],error)
assert len(result)==6,result
assert max(r['max_roll_mismatch_deg'] for r in result.values())<.001,result
path.with_suffix('.roll-validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
