"""Pinned-source idle-only vanilla four-MSE + existing COM2 objective switch."""
import ast
import hashlib
import json
import pickle
import sys
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

import yaml
import idle_leg_velocity5_20261029 as h

h.OUT = h.d.OUT / 'idle-vanilla-mse-20261030'


def prepare():
    plan = json.loads((h.d.OUT / 'getup-success-prepared.json').read_text())
    h.save('previous-plan', plan)
    assert plan['source']['sha256'] == 'c69818a578c659777cdf12aa32b0ff283ab775f21060ef32a5fc9f2a0b4a0769'
    with zipfile.ZipFile(plan['source']['local']) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    one = h.one
    s = entries['pipeline/perturbed_omni.py'].decode()
    s = one(s, "        self._perturb_cfg = dict(cfg)", """        self._perturb_cfg = dict(cfg)
        self._idle_mse_com2_only = bool(cfg.get('idle_vanilla_mse_com2_only', False))
        self._idle_mse_rows = (self._gaits[self._fixed_motion_ids] == -1) & ~self._recovery_rows""")
    s = one(s, "        self._phase_supervision_mask = (~(self._perturbed_rows | self._recovery_rows)).float()", """        self._phase_supervision_mask = (~(self._perturbed_rows | self._recovery_rows)).float()
        if self._idle_mse_com2_only:
            self._phase_supervision_mask *= ~self._idle_mse_rows""")
    s = one(s, "        self._prior = None if self._mse_only else MotionPrior(cfg['ae_directory'], len(self._prior_ids), self._device)", """        if self._idle_mse_com2_only:
            # Remove idle from AE history and its inference batch, not just its weight.
            prior_rows &= ~self._idle_mse_rows
            self._prior_ids = torch.where(prior_rows)[0]
            self._prior_index.fill_(-1)
            self._prior_index[self._prior_ids] = torch.arange(len(self._prior_ids), device=self._device)
        self._idle_extra_keep = torch.tensor([name == 'com2_velocity' for name in self.loss_term_names[4:]], device=self._device)
        self._prior = None if self._mse_only else MotionPrior(cfg['ae_directory'], len(self._prior_ids), self._device)""")
    s = one(s, "        self._tracking_mix[env_ids] = (~self._perturbed_rows[env_ids]).float()", """        self._tracking_mix[env_ids] = (~self._perturbed_rows[env_ids]).float()
        if self._idle_mse_com2_only:
            self._tracking_mix[env_ids] = torch.where(self._idle_mse_rows[env_ids], 1., self._tracking_mix[env_ids])""")
    # The supervision mask may now also exclude ordinary idle. Preserve phase inputs/targets.
    s = one(s, "return torch.where((self._phase_supervision_mask == 0)[:, None], self._feedback_phase, target)", "return torch.where((self._perturbed_rows | self._recovery_rows)[:, None], self._feedback_phase, target)")
    s = one(s, "        wobble = self._idle_wobble.append(vel, ang, self._final.last_kick, active)", "        wobble = (torch.zeros_like(self._time_buf) if self._idle_mse_com2_only else\n                  self._idle_wobble.append(vel, ang, self._final.last_kick, active))")
    s = one(s, "        return torch.cat((terms, foot_terms, leg_cost[:, None], wobble[:, None]), -1)", """        terms = torch.cat((terms, foot_terms, leg_cost[:, None], wobble[:, None]), -1)
        if self._idle_mse_com2_only:
            # Four original calibrated MSEs plus COM2; every other idle term is zero.
            terms[:, 4:] = torch.where(self._idle_mse_rows[:, None] & ~self._idle_extra_keep[None], 0., terms[:, 4:])
        return terms""")
    s = one(s, "        ids = self._perturbed_ids\n        prior_ids = self._prior_ids", "        vanilla_mse = terms[:, :4].clone() if self._idle_mse_com2_only else None\n        ids = self._perturbed_ids\n        prior_ids = self._prior_ids")
    s = one(s, "        # Extra early MSE shares AE's fade; the ordinary MSE handoff is unchanged.", """        if self._idle_mse_com2_only:
            self._tracking_mix.copy_(torch.where(self._idle_mse_rows, 1., self._tracking_mix))
        # Extra early MSE shares AE's fade; the ordinary MSE handoff is unchanged.""")
    s = one(s, "        if 'pelvis_velocity_extra' in self.loss_term_names:", """        if self._idle_mse_com2_only:
            # Restore the base terms before body x5, pelvis x10, pose x5 and handoff.
            terms[:, :4] = torch.where(self._idle_mse_rows[:, None], vanilla_mse, terms[:, :4])
        if 'pelvis_velocity_extra' in self.loss_term_names:""")
    s = one(s, "            self._com2_reward_values.copy_(torch.stack((factor, distance, angle), -1))", """            if self._idle_mse_com2_only:
                factor = torch.where(self._idle_mse_rows, 1., factor)
            self._com2_reward_values.copy_(torch.stack((factor, distance, angle), -1))""")
    s = one(s, '    def recovery_row_metadata(self, world):', '''    def recovery_row_metadata(self, world):
        result = self._base_recovery_row_metadata(world)
        if self._idle_mse_com2_only and bool(self._idle_mse_rows[world]):
            result.update(active_loss_terms=list(self.loss_term_names[:4])+['com2_velocity'],
                idle_vanilla_mse_com2_only=True, ae_disabled=True, ae_only=False,
                ae_tracking_only=False, ae_ticks=0, blend_ticks=0, ae_mse_weight=0.,
                prior_handoff_clock=None, prior_handoff_restart=None,
                auto_phase_supervised=False, pelvis_linear_velocity_multiplier=1.,
                all_rows_pelvis_velocity_mse_multiplier=1., perturbed_idle_pose_mse_multiplier=1.,
                head_reversal_weight=0., idle_wobble=None, foot_regularizers=None, leg_reversal=None,
                reward_definition='1/(1+four original calibrated MSEs+COM2); existing terminal penalties unchanged',
                reward_from_loss='reciprocal_sum',
                com2_reward_gate=dict(active=False, multiplier=1.))
            result['whole_body_velocity_mse']['multiplier'] = 1.
            result['whole_body_velocity_mse']['scope'] = 'All idle: original calibrated MSE; no body/pelvis boosts; full strength from tick0'
        return result

    def _base_recovery_row_metadata(self, world):''')
    s = one(s, "        result['perturbed_curriculum'] = dict(self._perturb_cfg)", """        result['perturbed_curriculum'] = dict(self._perturb_cfg)
        result['idle_objective_override'] = 'All idle: original four calibrated MSEs at full strength plus existing COM2; no other losses/multiplier or supervised phase loss. Existing position allowances and termination retained.'""")
    compile(s, 'perturbed_omni.py', 'exec')
    entries['pipeline/perturbed_omni.py'] = s.encode()
    cfg = yaml.safe_load(entries['prepared/env_config.yaml'])
    cfg['perturbed_motion']['idle_vanilla_mse_com2_only'] = True
    entries['prepared/env_config.yaml'] = yaml.safe_dump(cfg, sort_keys=False).encode()
    tree = ast.parse(entries['pipeline/train.py'])
    loop = next(n for n in ast.walk(tree) if isinstance(n, ast.For) and isinstance(n.iter, ast.List) and any(isinstance(x, ast.Constant) and x.value == 'engine_config.yaml' for x in n.iter.elts))
    class Args(SimpleNamespace):
        def __getattr__(self, key): return None
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(plan['checkpoint']['local']) as bundle:
        directory = Path(tmp)
        for name in ['engine_config.yaml', 'env_config.yaml', 'agent_config.yaml']:
            (directory/name).write_bytes(entries['prepared/'+name])
        exec(compile(ast.Module(body=[loop], type_ignores=[]), 'actual_resume', 'exec'), dict(yaml=yaml, bundle=bundle, directory=directory, config=cfg, a=Args(omni_run_lr=True, equipment_omni=True, resume_perturbed_motion=True)))
    source = h.OUT/'source.zip'
    with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, data in entries.items(): z.writestr(n, data)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    h.save('prepared', dict(plan, source=dict(local=str(source), sha256=sha, key='mimickit/pipeline_20261014/idle-vanilla-com2/source_'+sha[:12]+'.zip'), run_suffix='uefn_locomotion_idle_vanilla_com2_4000ada_2048'))
    changed = ['pipeline/perturbed_omni.py', 'prepared/env_config.yaml']
    with zipfile.ZipFile(source) as z, zipfile.ZipFile(h.OUT/'overlay.zip', 'w', zipfile.ZIP_DEFLATED) as delta:
        delta.writestr('infos.pkl', pickle.dumps(z.infolist()))
        for n in changed: delta.writestr(n, entries[n])
    test = """from pathlib import Path
import zipfile,py_compile
r=Path('/workspace/mimickit_trial/idle-vanilla-preflight');r.mkdir(exist_ok=True)
with zipfile.ZipFile('/workspace/mimickit_trial/idle-leg-source.zip') as z:z.extractall(r)
py_compile.compile(str(r/'pipeline/perturbed_omni.py'),doraise=True)
print('Staged source compiles')
"""
    (h.OUT/'test-gpu.py').write_text(test)
    h.save('delta', dict(files=changed, actual_resume_guard_passed=True))
    print(json.dumps(dict(source=sha, files=changed)))


def stop():
    assert json.loads((h.OUT/'preflight.json').read_text())['passed']
    h.stop()


def verify():
    (h.d.OUT/'latest-restart-receipt.txt').write_text(str(h.OUT))
    script = Path(__file__).with_name('verify_loco_unchanged_resume.py').read_text()
    script = h.one(script, "  assert yaml.safe_load(cp.read(name))==yaml.safe_load((p/name).read_text()),name", """  expected=yaml.safe_load(cp.read(name));actual=yaml.safe_load((p/name).read_text())
  if name=='env_config.yaml':expected['perturbed_motion']['idle_vanilla_mse_com2_only']=True
  assert expected==actual,name""")
    script = h.one(script, " assert row['frame_com2_reward_multiplier']", """ assert row['frame_com2_reward_multiplier']
 if row['idle_row']:
  assert row['idle_vanilla_mse_com2_only'] and row['ae_disabled'] and not row['auto_phase_supervised']
  assert row['whole_body_velocity_mse']['multiplier']==1.
  terms=z['loss_terms'+('' if i==0 else '_'+str(i))]
  extra=[j for j,n in enumerate(row['loss_term_names']) if n not in row['active_loss_terms']]
  assert (terms[:,extra]==0).all()
  assert all(v==1 for v in row['frame_com2_reward_multiplier'])""")
    scope = {'__name__': 'idle_vanilla_verify'}
    exec(compile(script, 'idle_vanilla_verify', 'exec'), scope)
    scope['main']()
    if json.loads((h.OUT/'live-verification.json').read_text())['ready']:
        print(h.r.remote("from pathlib import Path;Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch();print('Handoff verified')", timeout=20))


if __name__ == '__main__':
    action = sys.argv[1]
    (globals()[action] if action in ['prepare', 'verify', 'stop'] else getattr(h, action))()
