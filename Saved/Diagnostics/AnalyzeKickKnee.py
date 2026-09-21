import json,sys,collections,math
import numpy as np
from scipy.spatial.transform import Rotation
p=sys.argv[1]
d=json.load(open(p)); groups=collections.defaultdict(list)
for r in d['rows']:groups[r['agent']].append(r)
for agent,rows in groups.items():
    attacks=[r for r in rows if r['attack']]
    print(agent,'frames',len(rows),'attacks',collections.Counter(str(r['attack'][0]) for r in attacks),'first/last',[(r['n'],r['attack']) for r in attacks[:1]+attacks[-1:]])
    for side in ('l','r'):
        vals=[]
        for r in rows:
            b=r['meshes'].get('visible')
            if not b:continue
            hip,knee,ankle=[np.array(b[x+'_'+side]['p']) for x in ('thigh','calf','foot')]
            axis=ankle-hip; norm=np.linalg.norm(axis)
            if norm<1:continue
            axis/=norm; pole=knee-hip-axis*np.dot(knee-hip,axis);radius=np.linalg.norm(pole)
            if radius<1e-6:continue
            rot=Rotation.from_quat(b['pelvis']['q']).inv()
            vals.append((r,rot.apply(pole/radius),radius,np.array(b['calf_'+side]['q'])))
        peaks=[]
        for prev,now in zip(vals,vals[1:]):
            angle=math.degrees(math.acos(np.clip(np.dot(prev[1],now[1]),-1,1)))
            qa=math.degrees(2*math.acos(np.clip(abs(np.dot(prev[3],now[3])),0,1)))
            if min(prev[2],now[2])>3:peaks.append((angle,now[0]['n'],round(qa,2),round(now[2],2),now[0]['attack']))
        print(side,'pole frame jumps',sorted(peaks,reverse=True)[:6])
    spans=[];start=None;last=None
    for r in rows:
        key=str(r['attack'][0]) if r['attack'] else 'none'
        if key!=last:
            if last is not None:spans.append((start,r['n']-1,last))
            start=r['n'];last=key
    spans.append((start,rows[-1]['n'],last));print('spans',spans[:60])
