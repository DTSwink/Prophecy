"""Conservative local, unsaturated semi-implicit PD stability audit.

For frozen inertia M, spring K and damper D, inspect
lambda_max(h^2 K + 2 h D, M) < 4. This includes coupling through the
floating base. It is not a proof for contacts, large quaternion errors,
or moving inertia; recorded failures and physical stress remain required.
"""
import json
import numpy as np
import mujoco
from scipy.linalg import eigh
from scipy.spatial.transform import Rotation
from joint_pd import gains_for, OUT


def main():
    m=mujoco.MjModel.from_xml_path(str(OUT/'uefn.xml'));d=mujoco.MjData(m)
    meta=json.loads((OUT/'uefn.json').read_text());rng=np.random.default_rng(6301)
    qref=np.array(meta['reference_qpos']);poses=[qref]
    poses.extend(np.load(OUT/'rig-passive.npz')['qpos'])
    prefix=OUT/'runs/diagnose_05/failure-prefix.npz'
    if prefix.exists():poses.extend(np.load(prefix)['qpos'])
    for _ in range(256):
        q=qref.copy()
        for j in meta['joints']:
            angles=np.array(j['limits_rad']);a=rng.uniform(-1,1,3)
            a[np.array(j['modes'])==2]=0
            sy,sz=np.sin(angles[1:]/2)*a[1:]
            radius=max(1,np.linalg.norm(a[1:]));sy/=radius;sz/=radius
            rot=Rotation.from_quat([0,sy,sz,np.sqrt(1-sy*sy-sz*sz)])*Rotation.from_rotvec([a[0]*angles[0],0,0])
            qa=int(m.joint(j['name']).qposadr[0]);q[qa:qa+4]=rot.as_quat()[[3,0,1,2]]
        poses.append(q)
    k=np.zeros(m.nv);damping=k.copy();names=['root']*6
    gains=[]
    for j in meta['joints']:
        a=int(m.joint(j['name']).dofadr[0]);kp,kd,cap=gains_for(j['body'])
        k[a:a+3]=kp;damping[a:a+3]=kd;names.extend([j['body']]*3);gains.append((kp,kd,cap))
    matrix=np.diag(k/240**2+2*damping/240);M=np.empty((m.nv,m.nv));values=[]
    for q in poses:
        d.qpos[:]=q;mujoco.mj_forward(m,d);mujoco.mj_fullM(m,M,d.qM)
        values.append(float(eigh(matrix,M,eigvals_only=True,subset_by_index=[m.nv-1,m.nv-1])[0]))
    report={'passed':max(values)<3.2,'stability_boundary':4,'required_margin_boundary':3.2,
        'maximum':max(values),'pose_count':len(poses),'rig_sha256':meta['rig_sha256'],
        'joint_gains_kp_kd_max_nm':gains,'scope':__doc__}
    (OUT/'pd-mass-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));assert report['passed'],report


if __name__=='__main__':main()
