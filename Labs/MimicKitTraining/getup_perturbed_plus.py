"""Prepare the scheduled reset-velocity cohort in the pinned recovery source."""
import ast
import hashlib
import json
import zipfile
from pathlib import Path
import torch
import yaml
from getup_success_gates import replace_once

HELPER = '''def sample_getup_plus_velocities(root_pool, dof_pool, count, max_spin):
    """Separate source frames, isotropic axis, uniform angular speed in radians/s."""
    size = len(root_pool)
    a = torch.randint(size, (count,), device=root_pool.device)
    b = torch.randint(size-1, (count,), device=root_pool.device)
    b = b + (b >= a).long()
    axis = torch.randn((count, 3), device=root_pool.device)
    axis = axis / axis.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    spin = axis * (torch.rand((count, 1), device=root_pool.device) * max_spin)
    return root_pool[a], dof_pool[b], spin, a, b


'''

SETUP = '''        plus_fraction = float(cfg.get('getup_plus_fraction', 0.))
        self._perturbed_plus = random_start_rows(torch.where(self._perturbed_getup)[0],
            n, plus_fraction, self._recovery_fixed_motion)
        self._getup_low_head_ticks = torch.where(self._perturbed_plus,
            int(cfg.get('getup_plus_low_head_failure_tick', cfg['getup_low_head_failure_tick'])),
            int(cfg['getup_low_head_failure_tick']))
        self._plus_max_spin = math.radians(float(cfg.get('getup_plus_max_spin_degrees_s', 700.)))
        if not math.isfinite(self._plus_max_spin) or self._plus_max_spin < 0:
            raise ValueError('Invalid perturbed+ spin bound')
        self._plus_root_pool = self._motion_lib._frame_root_vel[self._loco_frame_pool]
        self._plus_dof_pool = self._motion_lib._frame_dof_vel[self._loco_frame_pool]
        if len(self._plus_root_pool) < 2 or not torch.isfinite(self._plus_root_pool).all() or not torch.isfinite(self._plus_dof_pool).all():
            raise ValueError('Invalid locomotion velocity pool')
        self._plus_linear_frame = torch.full((n,), -1, dtype=torch.long, device=self._device)
        self._plus_joint_frame = torch.full_like(self._plus_linear_frame, -1)
        self._plus_root_velocity = torch.zeros((n, 3), device=self._device)
        self._plus_spin = torch.zeros_like(self._plus_root_velocity)
'''

RESET = '''        plus = env_ids[self._perturbed_plus[env_ids]]
        if len(plus):
            linear, dof, spin, a, b = sample_getup_plus_velocities(
                self._plus_root_pool, self._plus_dof_pool, len(plus), self._plus_max_spin)
            # Animation translation is at the pelvis origin. Newton free-root
            # linear velocity is at its COM; account for the new independent spin.
            offset = q.quat_rotate(e.get_root_rot(char)[plus], self._body_com[plus, 0])
            e.set_root_vel(plus, char, linear + torch.cross(spin, offset, dim=-1))
            e.set_root_ang_vel(plus, char, spin)
            e.set_dof_vel(plus, char, dof)
            self._plus_linear_frame[plus] = self._loco_frame_pool[a]
            self._plus_joint_frame[plus] = self._loco_frame_pool[b]
            self._plus_root_velocity[plus] = linear
            self._plus_spin[plus] = spin
'''

META = '''        result['perturbed_plus_row'] = bool(self._perturbed_plus[world])
        if getup:
            result['getup_low_head_failure_tick'] = int(self._getup_low_head_ticks[world])
        if bool(self._perturbed_plus[world]):
            result.update(perturbation='whole-pose vanilla-to-limp blend; independent locomotion linear/joint velocities and random 3D spin',
                initial_linear_velocity_frame=int(self._plus_linear_frame[world]),
                initial_joint_velocity_frame=int(self._plus_joint_frame[world]),
                initial_pelvis_origin_velocity_m_s=self._plus_root_velocity[world].cpu().tolist(),
                initial_root_angular_velocity_rad_s=self._plus_spin[world].cpu().tolist(),
                initial_joint_velocity=self._motion_lib._frame_dof_vel[self._plus_joint_frame[world]].cpu().tolist())
'''

def patch(s):
    s=s.replace('\r\n','\n')
    s=replace_once(s, 'def getup_pelvis_failure(', HELPER+'def getup_pelvis_failure(')
    anchor='        self._loco_reset_dofs = self._motion_lib.joint_rot_to_dof(self._motion_lib._frame_joint_rot[self._loco_frame_pool])\n'
    s=replace_once(s,anchor,anchor+SETUP)
    s=replace_once(s,'        self._yaw_degrees[env_ids] = 0.\n',RESET+'        self._yaw_degrees[env_ids] = 0.\n')
    s=replace_once(s,"ticks >= self._perturb_cfg['getup_low_head_failure_tick']",'ticks >= self._getup_low_head_ticks')
    anchor='        if loco:\n'
    s=replace_once(s,anchor,META+anchor)
    s=replace_once(s,"result['getup_low_head_failure_tick'] = self._perturb_cfg['getup_low_head_failure_tick']", "result['getup_default_low_head_failure_tick'] = self._perturb_cfg['getup_low_head_failure_tick']")
    ast.parse(s)
    return s

def test():
    ns={'torch':torch};exec(HELPER,ns)
    torch.manual_seed(912)
    roots=torch.arange(300,dtype=torch.float32).reshape(100,3)
    dofs=torch.arange(1200,dtype=torch.float32).reshape(100,12)
    v,d,w,a,b=ns['sample_getup_plus_velocities'](roots,dofs,20000,700*torch.pi/180)
    assert (a!=b).all()
    torch.testing.assert_close(v,roots[a]);torch.testing.assert_close(d,dofs[b])
    speed=w.norm(dim=-1)*180/torch.pi
    assert speed.max()<=700.001 and abs(float(speed.mean())-350)<5
    assert (w/speed[:,None].clamp_min(1e-6)).mean(0).abs().max()<.001
    ticks=torch.tensor([79,80,99,100]);threshold=torch.tensor([80,100])
    assert (ticks[:,None]>=threshold).tolist()==[[False,False],[True,False],[True,False],[True,True]]
    return dict(samples=len(a),different_frames=True,spin_min=float(speed.min()),spin_max=float(speed.max()),spin_mean=float(speed.mean()),tick_boundaries=True)

def prepare():
    import resume_getup_success as r
    from backup import verified_readback
    plan=json.loads((r.OUT/'getup-success-prepared.json').read_text())
    (r.OUT/'getup-plus-previous-plan.json').write_text(json.dumps(plan,indent=2))
    with zipfile.ZipFile(plan['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    original=dict(entries)
    entries['pipeline/perturbed_omni.py']=patch(entries['pipeline/perturbed_omni.py'].decode()).encode()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml'])
    cfg['perturbed_motion'].update(getup_plus_fraction=.5,getup_plus_low_head_failure_tick=100,getup_plus_max_spin_degrees_s=700.)
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    archive=r.OUT/'getup-plus-source.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    result=test();result['changed_files']=[k for k in entries if entries[k]!=original[k]]
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    key='mimickit/pipeline_20261014/equipment/getup-plus/source_'+digest[:12]+'.zip'
    c=r.cloud.s3();c.put_object(Bucket=r.cloud.rp.VOLUME_ID,Key=key,Body=archive.read_bytes())
    verified_readback(c,r.cloud.rp.VOLUME_ID,key,digest)
    plan['source']=dict(local=str(archive),key=key,sha256=digest)
    plan['run_suffix']='uefn_getup_perturbed_plus_1024'
    (r.OUT/'getup-plus-prepared.json').write_text(json.dumps(plan,indent=2))
    (r.OUT/'getup-plus-tests.json').write_text(json.dumps(result,indent=2))
    local=Path(__file__).with_name('perturbed_omni.py');local.write_text(patch(local.read_text()),encoding='utf-8')
    print(json.dumps(result),flush=True)

if __name__=='__main__':prepare()
