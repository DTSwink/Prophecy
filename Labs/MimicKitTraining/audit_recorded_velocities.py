"""Compare recorded native-body velocities with CPU MuJoCo Jacobians.

Read-only replay diagnostic: no stepping, GPU use or live changes.
"""
import io
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation as R

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Saved/MimicKitEquipment/mixed-collapse-audit'


def main():
    source = zipfile.ZipFile(ROOT / 'Saved/MimicKitEquipment/mixed-getup-starts-source.zip')
    tree = ET.fromstring(source.read('assets/uefn/humanoid_uefn.xml'))
    tree.remove(tree.find('actuator'))
    for body in tree.iter('body'):
        joints = body.findall('joint')
        if len(joints) == 3:
            for joint in joints:
                body.remove(joint)
            ET.SubElement(body, 'joint', name=body.get('name')+'_ball', type='ball', limited='false')
    model = mujoco.MjModel.from_xml_string(ET.tostring(tree, encoding='unicode'))
    data = mujoco.MjData(model)
    names = json.loads(source.read('prepared/manifest.json'))['body_names']
    ids = [model.body(n).id for n in names]
    assert model.nv == 40 and len(ids) == 15
    z = zipfile.ZipFile(OUT / 'models.zip')
    rows = []
    with np.load(io.BytesIO(z.read('38799/replay.npz'))) as replay:
        meta = json.loads(str(replay['metadata']))
        for i, row in enumerate(meta['replay_rows']):
            suffix = '' if i == 0 else '_'+str(i)
            poses = replay['pose'+suffix]
            velocities = replay['world_velocities'+suffix]
            poserr, angerr, linerr, fd_angerr, adapter_errors = [], [], [], [], []
            for f in np.unique(np.linspace(1, len(poses)-1, min(12, len(poses)-1)).astype(int)):
                pose, vel = poses[f].astype(float), velocities[f].astype(float)
                data.qpos[:3] = pose[0, :3]
                data.qpos[3:7] = np.roll(pose[0, 3:], 1)
                data.qvel[:3] = vel[0, :3]
                data.qvel[3:6] = R.from_quat(pose[0, 3:]).inv().apply(vel[0, 3:6])
                for b, bid in enumerate(ids[1:], 1):
                    parent = ids.index(model.body_parentid[bid])
                    base = R.from_quat(pose[parent, 3:]) * R.from_quat(np.roll(model.body_quat[bid], -1))
                    relative = base.inv() * R.from_quat(pose[b, 3:])
                    joint = model.body_jntadr[bid]
                    qa, va = model.jnt_qposadr[joint], model.jnt_dofadr[joint]
                    # This inverts the native Newton FK path. The paired policy
                    # audit independently validates these raw qvel coordinates.
                    raw = base.inv().apply(vel[b, 3:6]-vel[parent, 3:6])
                    if model.jnt_type[joint] == mujoco.mjtJoint.mjJNT_BALL:
                        data.qpos[qa:qa+4] = np.roll(relative.as_quat(), 1)
                        data.qvel[va:va+3] = raw
                    else:
                        axis = model.jnt_axis[joint]
                        data.qpos[qa] = relative.as_rotvec() @ axis
                        data.qvel[va] = raw @ axis
                mujoco.mj_forward(model, data)
                poserr.append(np.max(np.abs(data.xpos[ids]-pose[:, :3])))
                lin, ang = [], []
                for bid in ids:
                    jp, jr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
                    mujoco.mj_jacBody(model, data, jp, jr, bid)
                    lin.append(jp @ data.qvel)
                    ang.append(jr @ data.qvel)
                lin, ang = np.array(lin), np.array(ang)
                # Independently evaluate the existing custom-engine adapter's
                # child-frame recursion, at body origins for this comparison.
                fixed_lin, fixed_ang = [data.qvel[:3].copy()], [vel[0, 3:6]]
                for b, bid in enumerate(ids[1:], 1):
                    parent = ids.index(model.body_parentid[bid])
                    joint = model.body_jntadr[bid]
                    va = model.jnt_dofadr[joint]
                    local = (data.qvel[va:va+3] if model.jnt_type[joint] == mujoco.mjtJoint.mjJNT_BALL
                             else model.jnt_axis[joint]*data.qvel[va])
                    fixed_ang.append(fixed_ang[parent]+R.from_quat(pose[b,3:]).apply(local))
                    fixed_lin.append(fixed_lin[parent]+np.cross(fixed_ang[parent], data.xpos[bid]-data.xpos[ids[parent]]))
                adapter_errors.append(float(max(np.max(np.abs(np.array(fixed_ang)-ang)),
                                                np.max(np.abs(np.array(fixed_lin)-lin)))))
                linerr.append(np.linalg.norm(lin-vel[:, :3], axis=1))
                angerr.append(np.linalg.norm(ang-vel[:, 3:6], axis=1))
                oldrot = R.from_matrix(data.xmat[ids].reshape(-1, 3, 3).copy())
                dt = 1e-6
                mujoco.mj_integratePos(model, data.qpos, data.qvel, dt)
                mujoco.mj_kinematics(model, data)
                newrot = R.from_matrix(data.xmat[ids].reshape(-1, 3, 3))
                finite = (newrot * oldrot.inv()).as_rotvec()/dt
                fd_angerr.append(float(np.max(np.abs(finite-ang))))
            angular = np.array(angerr)
            linear = np.array(linerr)
            rows.append(dict(row=i, clip=Path(row['motion_file']).stem,
                samples=len(poserr), max_pose_reconstruction_m=float(max(poserr)),
                angular_velocity_error_rms_rad_s=float(np.sqrt(np.mean(angular**2))),
                linear_velocity_error_rms_m_s=float(np.sqrt(np.mean(linear**2))),
                max_angular_velocity_error_rad_s=float(angular.max()),
                finite_difference_vs_jacobian_max_error=float(max(fd_angerr)),
                corrected_recursion_vs_jacobian_max_error=float(max(adapter_errors)),
                body_angular_error_rms=dict(zip(names, np.sqrt(np.mean(angular**2,axis=0)).tolist()))))
    result=dict(method='Recorded post-step qpos/qvel, CPU MuJoCo body Jacobians and quaternion finite difference; no physics steps', rows=rows)
    (OUT/'velocity-coordinates.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:max(row[k] for row in rows) for k in [
        'max_pose_reconstruction_m', 'angular_velocity_error_rms_rad_s',
        'linear_velocity_error_rms_m_s', 'finite_difference_vs_jacobian_max_error',
        'corrected_recursion_vs_jacobian_max_error']}))
    print(json.dumps([{k:r[k] for k in ['row','clip','angular_velocity_error_rms_rad_s','linear_velocity_error_rms_m_s']} for r in rows]))


if __name__ == '__main__':
    main()
