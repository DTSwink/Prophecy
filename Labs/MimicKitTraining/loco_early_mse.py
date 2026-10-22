"""Calibrate and add early MSE alongside the existing fading locomotion prior."""
import ast
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.spatial.transform import Rotation
import torch


def patch_source(source):
    old = "        # Perturbed rows use AE then body MSE, without an extra COM-band loss.\n        terms[:, :4] *= self._tracking_mix[:, None]\n"
    new = """        # Extra early MSE shares AE's fade; the ordinary MSE handoff is unchanged.
        mse_mix = self._tracking_mix
        early_weight = float(self._perturb_cfg.get('ae_mse_weight', 0.))
        if early_weight:
            mse_mix = mse_mix + early_weight * (1 - self._tracking_mix)
        terms[:, :4] *= mse_mix[:, None]
"""
    changes = [
        (old, new),
        ("terms[:, self.loss_term_names.index('pelvis_velocity_extra')] *= self._tracking_mix",
         "terms[:, self.loss_term_names.index('pelvis_velocity_extra')] *= mse_mix"),
        ("        self._tracking_mix = torch.ones(n, device=self._device)\n",
         "        self._tracking_mix = torch.ones(n, device=self._device)\n"
         "        early_weight = float(cfg.get('ae_mse_weight', 0.))\n"
         "        if not math.isfinite(early_weight) or early_weight < 0:\n"
         "            raise ValueError('Early AE-associated MSE weight must be finite and nonnegative')\n"),
        ("        result['perturbed_curriculum'] = dict(self._perturb_cfg)\n",
         "        result['perturbed_curriculum'] = dict(self._perturb_cfg)\n"
         "        if self._perturb_cfg.get('ae_mse_weight', 0.):\n"
         "            result['ae_mse_weight'] = float(self._perturb_cfg['ae_mse_weight'])\n"
         "            result['tracking_mse_multiplier'] = 'mix + ae_mse_weight * (1 - mix); AE multiplier remains 1 - mix'\n"
         "            result['objective'] += '; calibrated early MSE alongside AE, fading with AE during the existing handoff'\n"),
    ]
    for old, new in changes:
        if source.count(old) != 1:
            raise ValueError('Pinned source patch does not match: ' + old[:70])
        source = source.replace(old, new)
    compile(source, 'perturbed_omni.py', 'exec')
    return source


def body_mse(z, row, suffix):
    pose = z['pose' + suffix]
    target = z['reference_pose' + suffix]
    velocity = z['world_velocities' + suffix]
    delta = pose[..., :3] - target[..., :3]
    position = np.square(delta).mean((1, 2))
    leeway = row.get('position_mse_leeway')
    if leeway:
        if leeway.get('scope', 'all') != 'idle' or row['idle_row']:
            legs = np.array([n in leeway['leg_bodies'] for n in row['names']])
            leg = np.maximum(np.linalg.norm(delta[..., :2], axis=-1) - leeway['leg_horizontal_radius_m'], 0)**2
            leg += np.maximum(np.abs(delta[..., 2]) - leeway['leg_vertical_half_height_m'], 0)**2
            other = np.maximum(np.linalg.norm(delta, axis=-1) - leeway['other_radius_m'], 0)**2
            position = np.where(legs, leg, other).mean(-1) / 3
        elif leeway.get('locomotion_radius_m', 0) > 0:
            position = np.maximum(np.linalg.norm(delta, axis=-1) - leeway['locomotion_radius_m'], 0)**2
            position = position.mean(-1) / 3
    shape = (*pose.shape[:2], 3, 3)
    rotation = Rotation.from_quat(pose[..., 3:].reshape(-1, 4)).as_matrix().reshape(shape)
    target_rotation = Rotation.from_quat(target[..., 3:].reshape(-1, 4)).as_matrix().reshape(shape)
    values = np.stack([position,
        np.square(velocity[..., :3] - velocity[..., 6:9]).mean((1, 2)),
        np.square(rotation - target_rotation).mean((1, 2, 3)),
        np.square(velocity[..., 3:6] - velocity[..., 9:12]).mean((1, 2))], -1)
    names = ['position_mse', 'linear_velocity_mse', 'rotation_mse', 'angular_velocity_mse']
    return values * np.array([row['loss_weights'][n] for n in names])


def calibrate(replay):
    rows = []
    max_error = 0.
    checked = 0
    with np.load(replay, allow_pickle=False) as z:
        meta = json.loads(str(z['metadata']))
        for i, row in enumerate(meta['replay_rows']):
            suffix = '' if i == 0 else '_' + str(i)
            mse = body_mse(z, row, suffix)
            recorded = z['loss_terms' + suffix][:, :4]
            mix = np.asarray(row['frame_tracking_mix'])
            expected = mse * mix[:, None]
            error = float(np.abs(expected[1:] - recorded[1:]).max())
            max_error = max(max_error, error)
            if not np.allclose(expected[1:], recorded[1:], rtol=3e-4, atol=1e-5):
                raise ValueError(f'Reconstructed MSE disagrees with recorded terms: row {i}, max {error}')
            checked += len(mse) - 1
            if not row.get('perturbed_row') or row.get('recovery_row'):
                continue
            ticks = np.arange(len(mse))
            # Exclude reset and the first transition: three-pose AE history is not yet valid.
            select = (ticks >= 2) & (ticks < 30)
            prior = z['loss_terms' + suffix][:, row['loss_term_names'].index('motion_prior')]
            rows.append(dict(row=i, world=row['world'], idle=row['idle_row'], ticks=int(select.sum()),
                mse_sum=float(mse.sum(-1)[select].sum()), weighted_ae_sum=float(prior[select].sum())))
    count = sum(r['ticks'] for r in rows)
    mse_sum = sum(r['mse_sum'] for r in rows)
    ae_sum = sum(r['weighted_ae_sum'] for r in rows)
    if not count or not math.isfinite(mse_sum + ae_sum) or min(mse_sum, ae_sum) <= 0:
        raise ValueError('Insufficient valid early-frame calibration data')
    return dict(iteration=meta['iteration'], samples=meta['samples'], rows=rows,
        frames=count, mean_full_mse=mse_sum/count, mean_weighted_ae=ae_sum/count,
        ae_mse_weight=ae_sum/mse_sum, reconstructed_frames_checked=checked,
        max_reconstruction_error=max_error, fixed_weight=True,
        calibration='Existing deterministic replay, perturbed idle/loco ticks2..29; four weighted body MSE terms, current leeways and autoregressive targets; match mean weighted prior cost; no terminal penalties')


def check(source):
    """Execute the actual modified method across the handoff and unaffected cohorts."""
    class Base:
        def _tracking_losses(self, *args):
            return torch.full((4, 5), 2.)
    method = next(n for c in ast.parse(source).body if isinstance(c, ast.ClassDef)
                  for n in c.body if isinstance(n, ast.FunctionDef) and n.name == '_tracking_losses')
    from perturbed_motion import tracking_blend
    scope = dict(torch=torch, Base=Base, tracking_blend=tracking_blend,
                 EnvMode=SimpleNamespace(TRAIN=1), q=SimpleNamespace(quat_to_matrix=lambda x:x))
    cls = ast.ClassDef(name='Trial', bases=[ast.Name(id='Base', ctx=ast.Load())], keywords=[], body=[method], decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), 'actual-method', 'exec'), scope)
    for weight in (0., .25, 2.):
        for tick in (0, 2, 29, 30, 45, 59, 60, 120):
            e = scope['Trial']()
            vars(e).update(_perturb_ready=True, _refresh_reward_rotations=lambda:None,
                _perturbed_ids=torch.tensor([0,1,2]), _prior_ids=torch.tensor([0,1]),
                _prior=SimpleNamespace(append=lambda *a:None, cost=lambda:torch.tensor([5.,5.])),
                _prior_raw=torch.zeros(4), _time_buf=torch.full((4,), tick/30.), _mse_only=False,
                _perturb_cfg=dict(ae_ticks=30, blend_ticks=30, ae_mse_weight=weight),
                _perturbed_getup=torch.tensor([False,False,True,False]),
                _perturbed_rows=torch.tensor([True,True,True,False]), _idle_position_getup=True,
                _tracking_mix=torch.ones(4), _getup_position_weight=10., reward_target_pos=torch.zeros(4,15,3),
                _ae_weight=.2, _mode=0, _additive_head_reward=False,
                loss_term_names=('position_mse','linear_velocity_mse','rotation_mse','angular_velocity_mse','flat_com_velocity','motion_prior'))
            terms=e._tracking_losses(torch.ones(4,15,3), torch.ones(4,15,4), None,None,None,None)
            mix=max(0.,min(1.,(tick-30)/30))
            expected=torch.tensor([2*(mix+weight*(1-mix))]*4+[0.,1-mix])
            torch.testing.assert_close(terms[0],expected)
            torch.testing.assert_close(terms[1],expected)
            torch.testing.assert_close(terms[2],torch.tensor([10.,0,0,0,0,0]))
            torch.testing.assert_close(terms[3],torch.tensor([2.,2.,2.,2.,2.,0.]))
    return True
