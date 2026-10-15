"""Precompute compound drag and explicit inertia checks; no simulation/training."""
import json
from pathlib import Path
import numpy as np
import mujoco
from scipy.spatial.transform import Rotation
from build import transform, digest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def prepare():
    meta=json.loads((HERE/'limits.json').read_text())
    source=ROOT/meta.get('source_rig','Saved/Robotics/rig.json')
    rig=json.loads(source.read_text())
    assert digest(source)==meta['source_sha256']
    for name,source in meta['source_files'].items():assert digest(ROOT/name)==source['sha256']
    bodies={b['name']:b for b in rig['bodies']}
    basis=Rotation.from_euler('z',90,degrees=True).as_matrix()
    model=mujoco.MjModel.from_xml_path(str(HERE/'humanoid_uefn_physics.xml'))
    records={}
    for name,group in meta['groups'].items():
        i=model.body(name).id
        frame=meta['body_frames'][name]
        rot=Rotation.from_quat(frame['quaternion']).as_matrix()
        origin=np.array(frame['position'])
        com=model.body_ipos[i]
        coeff=0.; first=np.zeros(3); second=np.zeros((3,3)); members=[]
        for member in group['colliders_from']:
            b=bodies[member]
            assert b['angular_damping']==0, 'Nonzero source angular drag requires a validated Jolt mapping'
            source_com=transform(b['reference'])@transform(b['mass_frame'])
            r=rot.T@(basis@source_com[:3,3]-origin)-com
            c=b['jolt_mass_kg']*b['linear_damping']
            coeff+=c;first+=c*r;second+=c*(np.dot(r,r)*np.eye(3)-np.outer(r,r))
            members.append({'offset':r.tolist(),'coefficient':c})
        principal=Rotation.from_quat(model.body_iquat[i][[1,2,3,0]]).as_matrix()
        inertia=principal@np.diag(model.body_inertia[i])@principal.T
        records[name]=dict(mass=float(model.body_mass[i]),com=com.tolist(),inertia=inertia.tolist(),
                           drag_mass=coeff,drag_first=first.tolist(),drag_second=second.tolist(),members=members)
    result=dict(source_sha256=meta['source_sha256'],asset_sha256=digest(HERE/'humanoid_uefn.xml'),
                cancel_gyroscopic=True,bodies=records)
    (HERE/'physics.json').write_text(json.dumps(result,indent=2))
    return result

if __name__=='__main__':
    print('Prepared',len(prepare()['bodies']),'compound force records')
