"""Reference-calibrated extremity speed failure in the moving pelvis frame."""
import ast
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import torch
import yaml

BODIES = ['right_foot', 'left_foot', 'right_hand', 'left_hand']


def calibrate(archive, out):
    # Reuse the same model, interpolation and small-angle velocity correction
    # as production. This work is offline, not repeated during training.
    from prepare_perturbed_com2 import MJCFCharModel, MotionLib, JointType, mp_util, world_velocities
    torch.set_num_threads(1)
    mp_util.init(0, 1, 'cpu', 6793)
    source = out/'speed-reference-source'
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if name.startswith(('assets/uefn/', 'prepared/', 'motions/')):
                p = source/name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(z.read(name))
    for p in (source/'prepared').glob('*.yaml'):
        p.write_text(p.read_text().replace('/workspace/mimickit_trial', source.as_posix()))
    cfg = yaml.safe_load((source/'prepared/env_config.yaml').read_text())
    model = MJCFCharModel('cpu'); model.load(cfg['char_file'])
    lib = MotionLib(cfg['motion_file'], model, 'cpu')
    names = model.get_body_names(); ids_body = [names.index(n) for n in BODIES]
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
    rows = []
    for i in range(lib.get_num_motions()):
        duration = float(lib.get_motion_length(i))
        times = torch.arange(0., duration, 1/480.)
        ids = torch.full(times.shape, i, dtype=torch.long)
        root, rot, velocity, omega, joints, dof = lib.calc_motion_frame(ids, times)
        pos, rotation = model.forward_kinematics(root, rot, joints)
        frame = lib._calc_frame_blend(ids, times)[0]
        local = (dof@mapping).view(len(times), -1, 3)
        v, w = world_velocities(pos, rotation, velocity, omega*moving[frame, :1], local*moving[frame, 1:, None], parents)
        relative = v[:, ids_body] - v[:, :1] - torch.cross(w[:, :1].expand(-1, 4, -1), pos[:, ids_body]-pos[:, :1], dim=-1)
        speeds = relative.norm(dim=-1)
        maximum = speeds.amax(0)
        rows.append(dict(id=Path(lib.get_motion_file(i)).stem, max_m_s=maximum.tolist(),
            limits_m_s=(maximum*torch.tensor([1.35,1.35,1.5,1.5])).tolist(),
            motion_sha256=hashlib.sha256(Path(lib.get_motion_file(i)).read_bytes()).hexdigest()))
    report = dict(bodies=BODIES, ratios=[1.35,1.35,1.5,1.5], sample_hz=480,
        measurement='body-origin speed in translating AND rotating pelvis frame: norm(v-v_p-omega_p cross (p-p_p))',
        source_sha256=hashlib.sha256(Path(archive).read_bytes()).hexdigest(), motions=rows)
    (out/'extremity-speed-reference.json').write_text(json.dumps(report, indent=2))
    return report


METHOD = '''    def _extremity_speed_failure(self):
        char = self._get_char_id()
        ids = self._extremity_speed_ids
        pos = self._engine.get_body_pos(char)[:, ids]
        rot = self._engine.get_body_rot(char)[:, ids]
        ang = self._engine.get_body_ang_vel(char)[:, ids]
        vel = self._engine.get_body_vel(char)[:, ids] - torch.cross(
            ang, q.quat_rotate(rot, self._body_com[:, ids]), dim=-1)
        relative = vel[:, 1:] - vel[:, :1] - torch.cross(
            ang[:, :1].expand(-1, 4, -1), pos[:, 1:] - pos[:, :1], dim=-1)
        # Squared norms avoid a square root; rotation does not change length.
        too_fast = (relative.square().sum(-1) > self._extremity_speed_limits_sq[self._motion_ids]).any(-1)
        return too_fast & self._perturbed_rows & ~self._recovery_rows & (self._time_buf > 0)

'''


def patch_source(source):
    init = '''        self._extremity_speed_enabled = bool(cfg.get('extremity_speed_reference'))
        if self._extremity_speed_enabled:
            speed_table = json.loads(Path(cfg['extremity_speed_reference']).read_text())
            speed_names = speed_table['bodies']
            self._extremity_speed_ids = torch.tensor([names.index('pelvis')] + [names.index(n) for n in speed_names], device=self._device)
            entries_speed = {r['id']: r for r in speed_table['motions']}
            limits = [entries_speed[Path(self._motion_lib.get_motion_file(i)).stem]['limits_m_s'] for i in range(self._motion_lib.get_num_motions())]
            self._extremity_speed_limits = torch.tensor(limits, device=self._device)
            if not torch.isfinite(self._extremity_speed_limits).all() or (self._extremity_speed_limits < 0).any():
                raise ValueError('Invalid extremity speed reference limits')
            self._extremity_speed_limits_sq = self._extremity_speed_limits.square()
'''
    anchor = "        failed &= (self._gaits[self._motion_ids] != -1) & (ticks > self._perturb_cfg['grace_ticks'])\n"
    metadata = '''        if self._extremity_speed_enabled and not getup:
            result.update(timeout_only=False, extremity_speed_bodies=['right_foot','left_foot','right_hand','left_hand'],
                extremity_speed_limits_m_s=self._extremity_speed_limits[self._motion_ids[world]].cpu().tolist(),
                extremity_speed_frame='body origins relative to translating and rotating pelvis', extremity_speed_first_tick=1)
'''
    changes = [("        self._com2_targets = torch.tensor(targets, device=self._device)\n", "        self._com2_targets = torch.tensor(targets, device=self._device)\n"+init),
        ('    def _update_done(self):\n', METHOD+'    def _update_done(self):\n'),
        (anchor, anchor+"        if self._extremity_speed_enabled:\n            failed |= self._extremity_speed_failure()\n"),
        ("        if loco:\n            result['loco_failure_penalty']", metadata+"        if loco:\n            result['loco_failure_penalty']")]
    for old,new in changes:
        if source.count(old) != 1: raise ValueError('Speed patch anchor mismatch: '+old[:70])
        source = source.replace(old,new)
    compile(source, 'perturbed_omni.py', 'exec')
    return source


def check(source):
    from types import SimpleNamespace
    from prepare_perturbed_com2 import q
    cls = next(c for c in ast.parse(source).body if isinstance(c, ast.ClassDef))
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_extremity_speed_failure')
    scope = dict(torch=torch, q=q)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), 'actual-speed-method', 'exec'), scope)
    n=8
    pos=torch.randn(n,5,3); pos[:,0]=0
    rot=torch.zeros(n,5,4); rot[:,:,3]=1
    ang=torch.zeros(n,5,3); ang[:,:,2]=2
    origin_vel=torch.cross(ang,pos,dim=-1)+torch.tensor([2.,3.,4.])
    # Pure rigid translation/rotation must be zero in pelvis coordinates.
    com=torch.randn(n,5,3)*.1
    engine_vel=origin_vel+torch.cross(ang,com,dim=-1)
    e=SimpleNamespace(_get_char_id=lambda:0,_extremity_speed_ids=torch.arange(5),
        _body_com=com,_extremity_speed_limits_sq=torch.ones(n,4),_motion_ids=torch.arange(n),
        _perturbed_rows=torch.ones(n,dtype=torch.bool),_recovery_rows=torch.zeros(n,dtype=torch.bool),
        _time_buf=torch.ones(n),_engine=SimpleNamespace(get_body_pos=lambda _:pos,get_body_rot=lambda _:rot,
        get_body_ang_vel=lambda _:ang,get_body_vel=lambda _:engine_vel))
    failure=lambda:scope['_extremity_speed_failure'](e)
    assert not failure().any()
    engine_vel[0,1,0]+=.999
    engine_vel[1,2,0]+=1.001
    engine_vel[2,3,0]+=1.001
    engine_vel[3,4,0]+=1.001
    engine_vel[4:,1,0]+=2
    e._perturbed_rows[4]=False; e._recovery_rows[5]=True; e._time_buf[6]=0
    assert failure().tolist()==[False,True,True,True,False,False,False,True]
    # Exact equality passes (strict exceeds); isolate from cancellation error.
    pos.zero_();ang.zero_();com.zero_();engine_vel.zero_();engine_vel[:,1,0]=1
    assert not failure().any()
    # Run the real terminal path: new failures must zero-bootstrap, preserve
    # normal rows, and reuse (not duplicate) the existing loco penalty.
    from perturbed_motion import com2_velocity, com2_failure
    class Base:
        def _update_done(self): self._done_buf.zero_()
    done=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='_update_done')
    trial=ast.ClassDef(name='Trial',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=[method,done],decorator_list=[])
    flags=SimpleNamespace(**{k:SimpleNamespace(value=v) for k,v in [('NULL',0),('FAIL',1),('SUCC',2),('TIME',3)]})
    scope.update(Base=Base,DoneFlags=flags,EnvMode=SimpleNamespace(TRAIN=1),com2_velocity=com2_velocity,com2_failure=com2_failure)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[trial],type_ignores=[])),'actual-terminal-path','exec'),scope)
    t=scope['Trial']();vars(t).update(vars(e))
    vars(t).update(_perturb_ready=True,_extremity_speed_enabled=True,_episode_length=10.,
        _perturb_cfg=dict(episode_ticks=120,getup_ticks=180,grace_ticks=1000,min_speed_ratio=.7,loco_failure_penalty=100.),
        _perturbed_getup=torch.zeros(n,dtype=torch.bool),_gaits=torch.tensor([-1,0,0,0,0,0,0,0]),
        _head_id=0,_head_reset_height=torch.ones(n)*10,_com2_ids=[0],_com2_masses=torch.ones(1),_com2_targets=torch.ones(n,2),
        _done_buf=torch.zeros(n,dtype=torch.long),_reset_reason=torch.zeros(n,dtype=torch.long),_reward_buf=torch.ones(n),_mode=1,
        _outcome_ends=torch.zeros(n),_outcome_failures=torch.zeros(n),_outcome_head_resets=torch.zeros(n))
    engine_vel[:,1,0]=2
    t._update_done()
    assert t._done_buf.tolist()==[1,1,1,1,0,0,0,1]
    assert t._reward_buf.tolist()==[1,-99,-99,-99,1,1,1,-99]
    assert t._outcome_failures.tolist()==[1,1,1,1,0,0,0,1]
    t._extremity_speed_enabled=False;t._update_done();assert not t._done_buf.any()
    return dict(passed=True, tests=['rigid translation/rotation excluded','COM converted to origin',
        'either foot/hand','below/equal/above threshold','normal/recovery/reset exclusion',
        'actual FAIL path and counters','existing loco penalty only','default disabled'])


if __name__ == '__main__':
    import deploy_locomotion_branch as d
    plan=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    report=calibrate(plan['source']['local'],d.OUT)
    print(json.dumps(report))
