"""Patch the pinned recovery source and calibrate its additive AE cost."""
import json
from pathlib import Path
import numpy as np
import torch
from scipy.spatial.transform import Rotation
from perturbed_motion import MotionPrior


def patch_source(text):
    changes = [
        ("        prior_rows = self._perturbed_rows & ~self._perturbed_getup if self._idle_position_getup else self._perturbed_rows\n",
         "        prior_rows = self._perturbed_rows & ~self._perturbed_getup if self._idle_position_getup else self._perturbed_rows\n        if cfg.get('getup_ae_regularizer', False):\n            prior_rows |= self._perturbed_getup\n"),
        ("        ae = self._prior_raw*self._ae_weight*(1-self._tracking_mix)\n",
         "        ae = self._prior_raw*self._ae_weight*(1-self._tracking_mix)\n        if self._perturb_cfg.get('getup_ae_regularizer', False):\n            ae = torch.where(self._perturbed_getup, self._prior_raw*self._ae_weight, ae)\n"),
        ("            self._reward_buf[rows] = 1. - self.loss_terms[rows, 0]\n",
         "            self._reward_buf[rows] = 1. - self.loss_terms[rows, 0]\n            if self._perturb_cfg.get('getup_ae_regularizer', False):\n                self._reward_buf[rows] -= self.loss_terms[rows, self.loss_term_names.index('motion_prior')]\n"),
        ("                pelvis_linear_velocity_multiplier=1., getup_objective='idle_frame0_body_positions')\n",
         "                pelvis_linear_velocity_multiplier=1., getup_objective='idle_frame0_body_positions')\n            if self._perturb_cfg.get('getup_ae_regularizer', False):\n                result.update(active_loss_terms=['position_mse', 'motion_prior'], ae_disabled=False,\n                    getup_ae_regularizer=True, getup_ae_weight=self._ae_weight,\n                    reward_definition='1 - weighted position MSE - weighted AE cost')\n"),
        ("            result['perturbed_getup_reward_from_loss'] = self._getup_reward_form\n",
         "            result['perturbed_getup_reward_from_loss'] = self._getup_reward_form\n            if self._perturb_cfg.get('getup_ae_regularizer', False):\n                result['objective'] += '; additionally frozen three-pose AE regularizer on perturbed get-ups only'\n"),
    ]
    for old, new in changes:
        assert text.count(old) == 1
        text = text.replace(old, new)
    compile(text, 'perturbed_omni.py', 'exec')
    return text


def calibrate(replay, folder):
    torch.set_num_threads(4)
    prior = MotionPrior(folder, 1, 'cpu')
    contract = json.loads((Path(folder)/'body_contract.json').read_text())
    results=[]
    with np.load(replay, allow_pickle=False) as z:
        meta=json.loads(str(z['metadata']))
        assert meta['names']==contract['body_names'] and meta['fps']==30
        rows=meta.get('replay_rows',[meta])
        for i,row in enumerate(rows):
            if not row.get('perturbed_row') or not row.get('recovery_row'):continue
            suffix='' if i==0 else '_'+str(i)
            pose=z['pose'+suffix];loss=z['loss_terms'+suffix].sum(-1)
            if len(pose)<3:continue
            pos=torch.from_numpy(pose[:,:,:3].copy())
            rot=torch.from_numpy(Rotation.from_quat(pose[:,:,3:].reshape(-1,4)).as_matrix().reshape(-1,15,3,3).astype(np.float32))
            windows=torch.arange(len(pose)-2)[:,None]+torch.arange(3)[None,:]
            with torch.no_grad():raw=prior.scorer(prior.encode(pos[windows],rot[windows],ground_height=0.)).numpy()
            assert np.isfinite(raw).all() and np.isfinite(loss).all()
            results.append(dict(row=i,world=row['world'],ticks=len(pose)-1,
                loss_sum=float(loss[1:].sum()),raw_sum=float(raw.sum())))
    loss=sum(r['loss_sum'] for r in results);raw=sum(r['raw_sum'] for r in results)
    assert raw>0 and loss>0
    weight=loss/(9*raw)
    return dict(iteration=meta['iteration'],samples=meta['samples'],rows=results,
        calibration='Actual deterministic evaluation from resume checkpoint; perturbed get-ups only; valid consecutive 30Hz physical poses; terminal bonuses/penalties excluded',
        mean_body_loss=loss/sum(r['ticks'] for r in results),
        mean_ae_raw=raw/sum(r['ticks'] for r in results),weight=weight,
        ae_fraction=weight*raw/(loss+weight*raw),fixed_weight=True)
