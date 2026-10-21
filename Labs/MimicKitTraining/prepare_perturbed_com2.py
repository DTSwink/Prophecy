"""Precompute trunk COM targets from the exact stopped deployment, on CPU."""
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'Saved/MimicKitUEFN/dependencies'), str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
os.environ['PYGLET_HEADLESS'] = 'true'
import mujoco
import torch
import yaml
from anim.mjcf_char_model import MJCFCharModel
from anim.motion_lib import MotionLib
from anim.kin_char_model import JointType
from util import torch_util as q, mp_util
from absolute_walk import world_velocities
from perturbed_motion import COM2_BODIES, com2_velocity


def main():
    torch.set_num_threads(1)
    mp_util.init(0, 1, 'cpu', 6788)
    out = ROOT/'Saved/MimicKitEquipment/perturbed-preparation'
    source = out/'source'
    out.mkdir(exist_ok=True)
    archive = ROOT/'Exports/MimicKitEquipment/20261019_stopped_47039/training_source.zip'
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if name.startswith(('assets/uefn/', 'prepared/', 'motions/')):
                path = source/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(z.read(name))
    for path in (source/'prepared').glob('*.yaml'):
        path.write_text(path.read_text(encoding='utf-8').replace('/workspace/mimickit_trial', source.as_posix()), encoding='utf-8')
    cfg = yaml.safe_load((source/'prepared/env_config.yaml').read_text())
    model = MJCFCharModel('cpu')
    model.load(cfg['char_file'])
    lib = MotionLib(cfg['motion_file'], model, 'cpu')
    physics = mujoco.MjModel.from_xml_path(cfg['char_file'])
    names = model.get_body_names()
    body_ids = torch.tensor([names.index(n) for n in COM2_BODIES])
    mj_ids = [physics.body(n).id for n in names]
    masses = torch.tensor(physics.body_mass[mj_ids], dtype=torch.float32)[body_ids]
    weights = masses/masses.sum()
    com = torch.tensor(physics.body_ipos[mj_ids], dtype=torch.float32)
    parents = [int(p) for p in model._parent_indices]
    mapping = torch.zeros((model.get_dof_size(), (len(names)-1)*3))
    for j in range(1, len(names)):
        joint = model.get_joint(j)
        if joint.joint_type == JointType.SPHERICAL:
            mapping[joint.dof_idx:joint.dof_idx+3, (j-1)*3:j*3] = torch.eye(3)
        elif joint.joint_type == JointType.HINGE:
            mapping[joint.dof_idx, (j-1)*3:j*3] = joint.axis
    rotations = torch.cat((lib._frame_root_rot[:, None], lib._frame_joint_rot), 1)
    dot = (rotations*rotations.roll(-1, 0)).sum(-1).abs()
    moving = ((1-dot.square()).clamp_min(0).sqrt() >= .001) & (dot < 1)
    manifest = json.loads((source/'prepared/manifest.json').read_text())
    entries = {r['id']: r for r in manifest['motions']}
    rows = []
    for i in range(lib.get_num_motions()):
        duration = float(lib.get_motion_length(i))
        # Use midpoint quadrature: no duplicate seam or biased endpoint weight.
        intervals = max(1, round(duration*240))
        times = (torch.arange(intervals)+.5)*(duration/intervals)
        ids = torch.full((intervals,), i, dtype=torch.long)
        root, rot, velocity, omega, joints, dof = lib.calc_motion_frame(ids, times)
        pos, rotation = model.forward_kinematics(root, rot, joints)
        frame = lib._calc_frame_blend(ids, times)[0]
        local = (dof@mapping).view(intervals, -1, 3)
        v, w = world_velocities(pos, rotation, velocity, omega*moving[frame, :1],
            local*moving[frame, 1:, None], parents)
        vcom = v + torch.cross(w, q.quat_rotate(rotation, com.expand_as(pos)), dim=-1)
        trunk = com2_velocity(vcom[:, body_ids], weights)
        average = trunk.mean(0)
        name = Path(lib.get_motion_file(i)).stem
        entry = entries[name]
        if entry['gait'] != -1 and average.norm() < .01:
            raise ValueError('Locomotion COM2 average has no usable direction: '+name)
        rows.append(dict(motion_id=i, id=name, gait=entry['gait'], sword_drawn=entry['sword_drawn'],
            duration_s=duration, average_xy_m_s=average.tolist(), speed_m_s=float(average.norm()),
            sampled_speed_min_m_s=float(trunk.norm(dim=-1).min()),
            sampled_speed_max_m_s=float(trunk.norm(dim=-1).max()), samples=intervals,
            motion_sha256=hashlib.sha256(Path(lib.get_motion_file(i)).read_bytes()).hexdigest()))
    report = dict(source_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        bodies=list(COM2_BODIES), masses_kg=masses.tolist(), mass_weights=weights.tolist(),
        axes='fixed world XY horizontal, Z up',
        definition='Time average of mass-weighted body COM velocities over one full motion; midpoint quadrature at approximately 240 Hz; original animation velocity, not derivative of pelvis following',
        motions=rows)
    (out/'com2_targets.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    active = [r for r in rows if r['gait'] != -1]
    print(json.dumps(dict(motions=len(rows), locomotion=len(active),
        masses_kg=report['masses_kg'], speed_range_m_s=[min(r['speed_m_s'] for r in active), max(r['speed_m_s'] for r in active)],
        report=str(out/'com2_targets.json'))))


if __name__ == '__main__':
    main()
