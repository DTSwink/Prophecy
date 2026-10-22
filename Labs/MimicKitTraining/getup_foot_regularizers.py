"""Prepare opt-in ankle command/idle-local rotation costs in the exact live source."""
import ast
import hashlib
import json
import zipfile
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'Saved/MimicKitEquipment'

HELPER = '''@torch.jit.script
def getup_foot_costs(command: torch.Tensor, foot_rot: torch.Tensor,
                    calf_rot: torch.Tensor, idle_local: torch.Tensor):
    # Physical commanded ankle angular velocity, after the environment clamp.
    speed = command.square().mean(-1)
    local = q.quat_mul(q.quat_conjugate(calf_rot), foot_rot)
    delta = q.quat_mul(q.quat_conjugate(idle_local), local)
    # Shortest rotation angle; q and -q are the same orientation.
    angle = 2. * torch.atan2(delta[..., :3].norm(p=2, dim=-1), delta[..., 3].abs())
    return torch.stack((speed, angle.square().mean(-1)), -1)


'''

def once(s, old, new):
    if s.count(old) != 1:
        raise ValueError('Patch anchor must occur exactly once: '+old[:90])
    return s.replace(old, new)

def patch(s):
    s = s.replace('\r\n', '\n')
    s = once(s, 'def sample_getup_plus_velocities(', HELPER+'def sample_getup_plus_velocities(')
    anchor = '        self._idle_frame0_rot = body_rot.clone()\n'
    s = once(s, anchor, anchor+'''        foot_cfg = cfg.get('getup_foot_regularizers')
        self._foot_regularizers_enabled = foot_cfg is not None
        if self._foot_regularizers_enabled:
            if not self._idle_position_getup:
                raise ValueError('Foot regularizers require the idle-frame0 get-up objective')
            self._foot_cost_ids = [names.index('left_foot'), names.index('right_foot')]
            self._foot_calf_ids = [int(self._kin_char_model.get_parent_id(i)) for i in self._foot_cost_ids]
            if [names[i] for i in self._foot_calf_ids] != ['left_shin', 'right_shin']:
                raise ValueError('Expected each foot parent to be its calf')
            indices = []
            for i in self._foot_cost_ids:
                start = self._kin_char_model.get_joint_dof_idx(i)
                if self._kin_char_model.get_joint_dof_dim(i) != 3:
                    raise ValueError('Expected three velocity commands per ankle')
                indices.extend(range(start, start+3))
            self._foot_command_ids = indices
            self._foot_idle_local = q.quat_mul(q.quat_conjugate(body_rot[:, self._foot_calf_ids]), body_rot[:, self._foot_cost_ids])
            weights = [float(foot_cfg[k]) for k in ('velocity_weight', 'rotation_weight')]
            if not all(math.isfinite(w) and w > 0 for w in weights):
                raise ValueError('Foot loss weights must be finite and positive')
            self._foot_cost_weights = torch.tensor(weights, device=self._device)
''')
    anchor = '        self.loss_terms = torch.zeros((n, len(self.loss_term_names)), device=self._device)\n'
    s = once(s, anchor, '''        if self._foot_regularizers_enabled:
            self.loss_term_names = (*self.loss_term_names, 'feet_target_velocity', 'feet_idle_local_rotation')
            self.loss_weights['feet_target_velocity'] = weights[0]
            self.loss_weights['feet_idle_local_rotation'] = weights[1]
'''+anchor)
    anchor = '    def _tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):\n'
    s = once(s, anchor, '''    def _foot_regularizer_raw(self, rot):
        command = self._engine._controls.target_vel[self._get_char_id()][:, self._foot_command_ids]
        return getup_foot_costs(command, rot[:, self._foot_cost_ids], rot[:, self._foot_calf_ids],
                               self._foot_idle_local[self._motion_ids])

    def _tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):
        terms = self._base_perturbed_tracking_losses(pos, rot, vel, ang, target_vel, target_ang)
        if not self._perturb_ready or not self._foot_regularizers_enabled:
            return terms
        costs = self._foot_regularizer_raw(rot) * self._foot_cost_weights
        costs = torch.where(self._perturbed_getup[:, None], costs, 0.)
        return torch.cat((terms, costs), -1)

    def _base_perturbed_tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):
''')
    anchor = "                self._reward_buf[rows] -= self.loss_terms[rows, self.loss_term_names.index('motion_prior')]\n"
    s = once(s, anchor, anchor+'''            if self._foot_regularizers_enabled:
                self._reward_buf[rows] -= self.loss_terms[rows, -2:].sum(-1)
''')
    anchor = "                    reward_definition='1 - weighted position MSE - weighted AE cost')\n"
    s = once(s, anchor, anchor+'''            if self._foot_regularizers_enabled:
                result['active_loss_terms'] += ['feet_target_velocity', 'feet_idle_local_rotation']
                result['foot_regularizers'] = dict(self._perturb_cfg['getup_foot_regularizers'])
                result['reward_definition'] += ' - weighted ankle target-velocity cost - weighted ankle idle-local rotation cost'
''')
    anchor = "        result['perturbed_curriculum'] = dict(self._perturb_cfg)\n"
    s = once(s, anchor, anchor+'''        if self._foot_regularizers_enabled:
            result['foot_regularizers'] = dict(self._perturb_cfg['getup_foot_regularizers'])
            result['feet_target_velocity_definition'] = 'weight * mean of six squared clamped ankle motor target velocities, rad^2/s^2; perturbed get-ups including plus only'
            result['feet_idle_local_rotation_definition'] = 'weight * mean of two squared shortest foot-relative-calf rotation errors against assigned idle frame0, rad^2; perturbed get-ups including plus only'
''')
    s = s.replace("pure body-position MSE to assigned idle frame0, pelvis XY following, no deadbands or other losses", "body-position MSE to assigned idle frame0, pelvis XY following, no position deadbands")
    ast.parse(s)
    return s

def recorder_patch(s):
    s = s.replace('\r\n', '\n')
    old = "reward_definition='1 - weighted position MSE - terminal failure penalty + head-reset success bonus')"
    new = "reward_definition='1 - sum of recorded weighted physical loss terms - terminal failure penalty + standing success bonus')"
    return once(s, old, new)

def prepare():
    plan = json.loads((OUT/'getup-success-prepared.json').read_text())
    with zipfile.ZipFile(plan['source']['local']) as z:
        entries = {n:z.read(n) for n in z.namelist()}
    entries['pipeline/perturbed_omni.py'] = patch(entries['pipeline/perturbed_omni.py'].decode()).encode()
    entries['pipeline/observe.py'] = recorder_patch(entries['pipeline/observe.py'].decode()).encode()
    cfg = yaml.safe_load(entries['prepared/env_config.yaml'])
    cfg['perturbed_motion']['getup_foot_regularizers'] = dict(velocity_weight=1., rotation_weight=1.,
        target_fraction_each=.07, fixed_weights=True, scope='perturbed get-ups including perturbed+',
        calibration_pending=True)
    entries['prepared/env_config.yaml'] = yaml.safe_dump(cfg, sort_keys=False).encode()
    path = OUT/'getup-foot-candidate.zip'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items(): z.writestr(n,data)
    (OUT/'getup-foot-previous-plan.json').write_text(json.dumps(plan, indent=2))
    # Preserve concurrent locomotion edits: apply only optional changes to shared source.
    for name, transform in [('perturbed_omni.py',patch),('observe.py',recorder_patch)]:
        p=Path(__file__).with_name(name);p.write_text(transform(p.read_text()),encoding='utf-8')
    print(json.dumps(dict(candidate=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())))

if __name__ == '__main__': prepare()
