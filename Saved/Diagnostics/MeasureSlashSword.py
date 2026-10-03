import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
d=json.loads(Path(sys.argv[1]).read_text());old={};exits={};out={}
for row in d['rows']:
    a=row['agent'];prev=old.get(a);old[a]=row
    if prev and 'ATTACKING' in prev['state'] and 'LOCOMOTION' in row['state']:exits[a]=row['frame']
    if a not in exits or 'LOCOMOTION' not in row['state'] or not row.get('weapon'):continue
    b=row['bones'];v=lambda n:np.array(b[n][0][:3]);up=v('neck_01')-v('pelvis');up/=np.linalg.norm(up)
    right=v('upperarm_r')-v('upperarm_l');w=np.linalg.norm(right)/2;right-=up*np.dot(up,right);right/=np.linalg.norm(right)
    m=np.stack([np.cross(right,up),right,up]);o=(v('upperarm_r')+v('upperarm_l'))/2
    hand=m@(v('hand_r')-o);q=R.from_quat(b['hand_r'][0][3:]);weapon=row['weapon'];g=R.from_quat(weapon['grip'][3:])
    lo=np.array(weapon['min']);hi=np.array(weapon['max']);axis=np.argmax(hi-lo);scale=np.array(weapon['scale']);p0=(lo+hi)*.5;p1=p0.copy();p0[axis]=lo[axis];p1[axis]=hi[axis]
    p0=np.array(weapon['grip'][:3])+g.apply(p0*scale);p1=np.array(weapon['grip'][:3])+g.apply(p1*scale)
    if np.linalg.norm(p0)>np.linalg.norm(p1):p0,p1=p1,p0
    start=hand+m@q.apply(p0);end=hand+m@q.apply(p1);direction=end-start
    heading=np.arctan2(direction[1],direction[0])*180/np.pi
    score=1000
    for t in np.linspace(0,1,301):
        p=start+(end-start)*t
        if -3*w<p[2]<.7*w:score=min(score,(p[0]/(.9*w+3))**2+(p[1]/(w+3))**2)
    key=f'{a}:{exits[a]}';z=out.setdefault(key,{'minimum_blade_clearance':1000,'samples':[]})
    z['minimum_blade_clearance']=min(z['minimum_blade_clearance'],float(score))
    z['samples'].append([row['frame']-exits[a],*np.round(hand,2),round(heading,2),round(float(score),3)])
for z in out.values():
    headings=np.unwrap(np.deg2rad([s[4] for s in z['samples']]))*180/np.pi
    z['total_heading_change']=float(headings[-1]-headings[0]);z['max_heading_step']=float(np.max(np.abs(np.diff(headings)))) if len(headings)>1 else 0
    z['samples']=z['samples'][::8]
print(json.dumps(out,indent=1));Path(sys.argv[1]).with_suffix('.sword-metrics.json').write_text(json.dumps(out,indent=2))
