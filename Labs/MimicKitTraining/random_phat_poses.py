"""Independent PHAT-admissible poses for review, never a training deployment."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from scipy.spatial.transform import Rotation as R
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'Labs/CrawlTraining'), str(ROOT/'Labs/MimicKitUEFN'),
               str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
from current_phat import current_source
from anim.mjcf_char_model import MJCFCharModel
from test_model import coords, violation


def main():
    meta = current_source()
    out = ROOT/'Saved/MimicKitEquipment/random-phat-poses'
    out.mkdir(exist_ok=True)
    count, sample_count, seed = 1000, 1500, 20261020
    # Preserve the first 1,000 poses from the original joint-by-joint RNG stream.
    rng = np.random.default_rng(seed)
    torch.set_num_threads(1)
    model = MJCFCharModel('cpu')
    model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    names = model.get_body_names()
    dofs = np.zeros((sample_count, model.get_dof_size()), np.float32)
    constraint_rows = []
    checks = []
    for j in meta['joints']:
        joint = model.get_joint(names.index(j['body']))
        d = joint.dof_idx
        ref = R.from_quat(np.array(j['reference_wxyz'])[[1, 2, 3, 0]])
        if j['kind'] == 'ball':
            assert j['modes'] == [1, 1, 1], 'Explicit sampler needed for a changed axis mode'
            limits = np.asarray(j['limits_rad'])
            twist = rng.uniform(-limits[0], limits[0], sample_count)
            angle = rng.uniform(0, 2*np.pi, sample_count)
            radius = np.sqrt(rng.uniform(0, 1, sample_count))
            y = radius*np.cos(angle)*np.sin(limits[1]/2)
            z = radius*np.sin(angle)*np.sin(limits[2]/2)
            w = np.sqrt(1-y*y-z*z)
            c, s = np.cos(twist/2), np.sin(twist/2)
            allowed = R.from_quat(np.column_stack((w*s, y*c+z*s, z*c-y*s, w*c)))
            dofs[:, d:d+3] = (ref.inv()*allowed).as_rotvec()
            # Validate the actual float32 representation that consumers load.
            actual = ref*R.from_rotvec(dofs[:, d:d+3])
        else:
            # Same one-axis hinge convention as the existing PHAT/Jolt audit:
            # exported connector quaternions contain sub-0.001-degree residue
            # on the two locked axes, which are absent from the actual hinge.
            ref_vector = ref.as_rotvec()
            assert np.linalg.norm(ref_vector[:2]) < 1e-5
            ref = R.from_rotvec([0., 0., ref_vector[2]])
            dofs[:, d] = rng.uniform(*j['range_rad'], sample_count)
            actual = ref*R.from_rotvec(dofs[:, d, None]*joint.axis.numpy())
        q = actual.as_quat()[:count, [3, 0, 1, 2]]
        bad = violation(coords(q), j)
        if bad.any():
            raise RuntimeError(f"{j['body']}: {bad.sum()} inadmissible poses")
        checks.append(dict(body=j['body'],poses=count,violations=int(bad.sum())))
        constraint_rows.extend([[len(constraint_rows)+i, *j['modes'], *j['limits_rad'], *v]
                                for i, v in enumerate(q)])
    dofs = dofs[:count].copy()
    root_pos = np.tile([0., 0., meta['body_frames']['pelvis']['position'][2]], (count, 1)).astype(np.float32)
    root_quat = np.tile([0., 0., 0., 1.], (count, 1)).astype(np.float32)
    with torch.no_grad():
        positions, rotations = model.forward_kinematics(torch.from_numpy(root_pos),
            torch.from_numpy(root_quat), model.dof_to_rot(torch.from_numpy(dofs)))
    poses = torch.cat((positions, rotations), -1).numpy()
    np.testing.assert_array_equal(poses[:, 0, :3], root_pos)
    np.testing.assert_array_equal(poses[:, 0, 3:], root_quat)
    # Independent check against the project's actual Jolt limit implementation.
    src, dst = out/'joint-limits-input.csv', out/'joint-limits-jolt.csv'
    np.savetxt(src, constraint_rows, delimiter=',', fmt=['%d']*4+['%.12g']*7,
               header='index,m0,m1,m2,a,b,c,w,x,y,z', comments='')
    env = dict(os.environ)
    env['PATH'] = str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env['PATH']
    subprocess.run([str(ROOT/'Saved/Robotics/jolt_probe.exe'), '--limits', str(src), str(dst)],
                   env=env, check=True, capture_output=True)
    result = np.genfromtxt(dst, delimiter=',', names=True)
    assert len(result) == count*len(meta['joints'])
    assert np.all(result['mask'] == 0), 'Jolt rejected sampled joint rotations'
    bodies = []
    clearances = []
    for name in names:
        frame = meta['body_frames'][name]
        rest = R.from_quat(frame['quaternion'])
        shapes = []
        i = names.index(name)
        for g in [x for x in meta['geometry'] if x['body'] == name]:
            pos = rest.inv().apply(np.array(g['position'])-frame['position'])
            rot = rest.inv()*R.from_quat(g['quaternion'])
            shapes.append(dict(type=g['type'],size=g['size'],pos=pos.tolist(),quat=rot.as_quat().tolist()))
            world_rot = R.from_quat(poses[:, i, 3:])*rot
            centre = poses[:, i, :3]+R.from_quat(poses[:, i, 3:]).apply(pos)
            size = np.array(g['size'])
            extent = (np.abs(world_rot.as_matrix()[:, 2])@size if g['type']=='box'
                      else size[0]+size[1]*abs(world_rot.as_matrix()[:, 2, 2]) if g['type']=='capsule'
                      else np.full(count, size[0]))
            clearances.append(centre[:, 2]-extent)
        bodies.append(dict(name=name,shapes=shapes))
    minimum = np.min(clearances, axis=0)
    path = out/'corpus.npz'
    np.savez_compressed(path, dof=dofs, root_position=root_pos, root_quaternion_xyzw=root_quat,
        body_pose_xyz_xyzw=poses, dof_velocity=np.zeros_like(dofs),
        root_linear_velocity=np.zeros_like(root_pos),root_angular_velocity=np.zeros_like(root_pos),
        body_names=np.array(names),minimum_floor_clearance_m=minimum)
    report = dict(count=count,seed=seed,sampling_pool_count=sample_count,
        retained_original_pose_range=[1,count],body_count=len(names),dof_count=model.get_dof_size(),
        pelvis_position_m=root_pos[0].tolist(),pelvis_quaternion_xyzw=[0,0,0,1],
        sampling='Independent uniform twist and hinge coordinates; uniform area inside each coupled swing ellipse; no pose rejection or curation.',
        collision_processing='None: self-overlap and floor penetration are not filtered or corrected.',
        poses_below_floor=int((minimum<0).sum()),joint_checks=checks,jolt_checks=len(result),
        jolt_violations=int((result['mask']!=0).sum()),training_deployed=False,
        limits_sha256=hashlib.sha256((ROOT/'Labs/MimicKitUEFN/limits.json').read_bytes()).hexdigest(),
        source_files=meta['source_files'],corpus_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (out/'report.json').write_text(json.dumps(report,indent=2))
    (out/'data.json').write_text(json.dumps(dict(report=report,bodies=bodies,
        poses=poses.tolist(),minimum_floor_clearance_m=minimum.tolist()),separators=(',',':')))
    print(json.dumps({k:report[k] for k in ['count','jolt_checks','jolt_violations','poses_below_floor','corpus_sha256']}))


if __name__ == '__main__':
    main()
