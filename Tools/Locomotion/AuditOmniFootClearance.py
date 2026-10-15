"""Measure actual foot-collider bottom, not bone height or screenshots."""
from pathlib import Path
import json
import itertools
import numpy as np
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[2]

def bottom(poses,shape,index):
    pose=poses[:,index]
    body_r=Rotation.from_quat(pose[:,3:]).as_matrix()
    rot=body_r@Rotation.from_quat(shape['quaternion']).as_matrix()
    center=pose[:,:3]+np.einsum('nij,j->ni',body_r,shape['position'])
    assert shape['type']=='box'
    low=center[:,2]-np.abs(rot[:,2,:])@np.asarray(shape['size'])
    # Independent eight-corner computation guards half/full-extent mistakes.
    corners=np.array(list(itertools.product((-1,1),repeat=3)))*shape['size']
    vertices=center[:,None,:]+np.einsum('nij,kj->nki',rot,corners)
    np.testing.assert_allclose(low,vertices[:,:,2].min(1),atol=1e-12)
    return low,center,rot

def main():
    data=json.loads((ROOT/'Labs/MimicKitUEFN/omni-preview.json').read_text())
    rows=[]
    for clip in data['clips']:
        for side in ['left','right']:
            original_name='foot_'+side[0];reduced_name=side+'_foot'
            original_shape=next(s for s in data['source_geometry'] if s['body']==original_name)
            reduced_shape=next(s for s in data['geometry'] if s['body']==reduced_name)
            a,ap,ar=bottom(np.array(clip['source']),original_shape,data['source_names'].index(original_name))
            b,bp,br=bottom(np.array(clip['reduced']),reduced_shape,data['names'].index(reduced_name))
            extra=np.maximum(-b,0)-np.maximum(-a,0)
            tick=int(extra.argmax())
            rows.append(dict(clip=clip['label'],side=side,
                original_max_penetration_cm=float(max(0,-a.min())*100),
                retarget_max_penetration_cm=float(max(0,-b.min())*100),
                worst_added_penetration_cm=float(extra[tick]*100),tick=tick,
                original_bottom_at_tick_cm=float(a[tick]*100),retarget_bottom_at_tick_cm=float(b[tick]*100),
                center_shift_at_tick_cm=((bp[tick]-ap[tick])*100).tolist(),
                max_foot_rotation_difference_deg=float(np.rad2deg(Rotation.from_matrix(np.swapaxes(ar,-1,-2)@br).magnitude()).max()),
                original_below_floor_frames=int((a<-.00001).sum()),retarget_below_floor_frames=int((b<-.00001).sum())))
    report=dict(floor_z_m=0,method='Exact box support height; checked against all eight transformed corners',rows=rows)
    (ROOT/'Saved/MimicKitUEFN/omni-foot-clearance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(sorted(rows,key=lambda r:r['worst_added_penetration_cm'],reverse=True)[:6],indent=2))
    print('Walk LR:',json.dumps([r for r in rows if r['clip']=='Walk · LR']))
    print('Affected clips',len({r['clip'] for r in rows if r['worst_added_penetration_cm']>.1}))
if __name__=='__main__':main()
