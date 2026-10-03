import json,sys,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
c=json.loads(Path('Content/locomotion/NN/prophecy_slash_native.json').read_text(encoding='utf-8'))
def unit(v):return v/max(np.linalg.norm(v),1e-12)
def basis(axis,pole):
    axis=unit(axis);side=unit(pole-axis*np.dot(axis,pole));up=unit(np.cross(axis,side))
    return np.stack([axis,unit(np.cross(up,axis)),up],axis=1)
def degrees(r):return float(np.degrees(r.magnitude()))
for path in sys.argv[1:]:
    data=json.loads(Path(path).read_text());result={}
    for i,s in enumerate(('l','r')):
        limb=c['full_limbs'][i];mirror=np.array([1,-1,1])
        axis=np.array(c['full_geometry']['local_offsets'][limb['end']])*mirror
        p0=np.array(c['full_geometry']['ik_local_pole_axis'][i][0])*mirror
        p1=np.array(c['full_geometry']['ik_local_pole_axis'][i][1])*mirror
        rows=[]
        for row in data['rows']:
            if 'ATTACKING' not in row['state']:continue
            b=row['bones'];a=np.array(b['upperarm_'+s][0]);m=np.array(b['lowerarm_'+s][0]);h=np.array(b['hand_'+s][0])
            ar,mr,hr=R.from_quat(a[3:]),R.from_quat(m[3:]),R.from_quat(h[3:])
            target=unit(h[:3]-m[:3]);start=hr.apply(unit(axis));cross=np.cross(start,target);dot=np.dot(start,target)
            if dot<-.999999:continue
            swing=R.from_quat(np.r_[cross,1+dot]/np.linalg.norm(np.r_[cross,1+dot]));desired=swing*hr
            pole=R.from_matrix(basis(target,ar.apply(p0))@basis(axis,p1).T)
            rows.append({'frame':row['frame'],'wrist_roll_mismatch_deg':degrees(mr.inv()*desired),'upper_pole_error_deg':degrees(mr.inv()*pole),
                'aim_error_deg':float(np.degrees(np.arccos(np.clip(np.dot(mr.apply(unit(axis)),target),-1,1))))})
        result[s]={'samples':len(rows),'stats':{k:{'max':max(x[k] for x in rows),'median':float(np.median([x[k] for x in rows]))} for k in ('wrist_roll_mismatch_deg','upper_pole_error_deg','aim_error_deg')},'largest':sorted(rows,key=lambda x:x['wrist_roll_mismatch_deg'],reverse=True)[:3]}
    print(json.dumps({'capture':path,'results':result},indent=2))
