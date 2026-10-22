"""Replace extremity-speed failure with a calibrated squared excess cost."""
import ast
import io
import json
import zipfile
from pathlib import Path
import numpy as np


def calibrate(checkpoint, reference):
    with zipfile.ZipFile(checkpoint) as z:
        with np.load(io.BytesIO(z.read('replay.npz')), allow_pickle=False) as replay:
            metadata=json.loads(str(replay['metadata']))
            names=metadata['names'];ids=[names.index(n) for n in reference['bodies']]
            refs={r['id']:r for r in reference['motions']}
            raw=[];base=[];rows=[]
            for i,row in enumerate(metadata['replay_rows']):
                if not row.get('perturbed_row') or row.get('recovery_row'):continue
                suffix='' if i==0 else '_'+str(i)
                pos=replay['pose'+suffix][...,:3]
                vel=replay['world_velocities'+suffix][...,:3]
                ang=replay['world_velocities'+suffix][...,3:6]
                relative=vel[:,ids]-vel[:,:1]-np.cross(ang[:,:1],pos[:,ids]-pos[:,:1])
                speed=np.linalg.norm(relative,axis=-1)
                limits=np.array(refs[Path(row['motion_file']).stem]['limits_m_s'])
                cost=np.square(np.maximum(speed-limits,0)).mean(-1)
                existing=replay['loss_terms'+suffix].sum(-1)
                # Exclude the synthetic reset frame (not an action/reward).
                raw.extend(cost[1:]);base.extend(existing[1:])
                rows.append(dict(motion=row['motion_file'],frames=len(cost)-1,violating_frames=int((cost[1:]>0).sum())))
            raw=np.array(raw);base=np.array(base)
            if len(raw)==0 or raw.mean()<=0:raise ValueError('No speed excess available for calibration')
            active=raw>0
            weight=.15*base[active].mean()/raw[active].mean()
            return dict(weight=float(weight),baseline_mean=float(base[active].mean()),raw_excess_mean=float(raw[active].mean()),
                weighted_excess_mean=float(weight*raw[active].mean()),target_ratio=.15,frames=len(raw),
                all_frames_baseline_mean=float(base.mean()),all_frames_weighted_excess_mean=float(weight*raw.mean()),
                violating_frames=int((raw>0).sum()),replay_iteration=metadata['iteration'],rows=rows,
                definition='mean over four limbs of max(speed-limit,0)^2; fixed coefficient calibrated on violating frames of pre-termination checkpoint replay')


METHOD='''    def _append_extremity_speed_loss(self, terms, pos, vel, ang):
        weight = float(self._perturb_cfg.get('extremity_speed_loss_weight', 0.))
        if not weight:
            return terms
        ids = self._extremity_speed_ids[1:]
        # Reward already supplies body-origin world velocities, not COM velocities.
        relative = vel[:, ids] - vel[:, :1] - torch.cross(
            ang[:, :1].expand(-1, 4, -1), pos[:, ids] - pos[:, :1], dim=-1)
        excess = (relative.norm(dim=-1) - self._extremity_speed_limits[self._motion_ids]).clamp_min(0.)
        cost = excess.square().mean(-1) * weight
        cost = torch.where(self._perturbed_rows & ~self._recovery_rows, cost, 0.)
        return torch.cat((terms, cost[:, None]), -1)

'''


def patch_source(source):
    init='''        speed_weight = float(cfg.get('extremity_speed_loss_weight', 0.))
        if not math.isfinite(speed_weight) or speed_weight < 0:
            raise ValueError('Extremity speed loss weight must be finite and nonnegative')
        if speed_weight:
            if not self._extremity_speed_enabled:
                raise ValueError('Extremity speed loss requires reference limits')
            self.loss_term_names = (*self.loss_term_names, 'extremity_speed_excess')
            self.loss_weights['extremity_speed_excess'] = speed_weight
'''
    pairs=[
        ('        self.loss_terms = torch.zeros((n, len(self.loss_term_names)), device=self._device)\n',init+'        self.loss_terms = torch.zeros((n, len(self.loss_term_names)), device=self._device)\n'),
        ('    def _tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):\n',METHOD+'    def _tracking_losses(self, pos, rot, vel, ang, target_vel, target_ang):\n'),
        ('return torch.cat((terms, ae[:, None]), -1)','return self._append_extremity_speed_loss(torch.cat((terms, ae[:, None]), -1), pos, vel, ang)'),
        ('return torch.cat((terms, ae[:, None], head_loss[:, None]), -1)','return self._append_extremity_speed_loss(torch.cat((terms, ae[:, None], head_loss[:, None]), -1), pos, vel, ang)'),
        ('        if self._extremity_speed_enabled:\n            failed |= self._extremity_speed_failure()','        if self._extremity_speed_enabled and self._perturb_cfg.get(\'extremity_speed_termination\', True):\n            failed |= self._extremity_speed_failure()'),
        ("            result.update(timeout_only=False, extremity_speed_bodies=", "            result.update(timeout_only=not loco and not self._perturb_cfg.get('extremity_speed_termination', True), extremity_speed_bodies="),
        ("        result['perturbed_curriculum'] = dict(self._perturb_cfg)\n", "        result['perturbed_curriculum'] = dict(self._perturb_cfg)\n"
         "        result['extremity_speed_termination'] = bool(self._extremity_speed_enabled and self._perturb_cfg.get('extremity_speed_termination', True))\n"
         "        result['extremity_speed_loss_weight'] = float(self._perturb_cfg.get('extremity_speed_loss_weight', 0.))\n"
         "        result['extremity_speed_loss_definition'] = 'weight * mean(max(pelvis-relative limb speed - limit, 0)^2); perturbed idle/loco only, no fade'\n")]
    for old,new in pairs:
        if source.count(old)!=1:raise ValueError('Patch anchor mismatch: '+old[:80])
        source=source.replace(old,new)
    compile(source,'perturbed_omni.py','exec')
    return source


def test(source):
    import torch
    from types import SimpleNamespace
    cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef))
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_append_extremity_speed_loss')
    ns=dict(torch=torch);exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),'actual-speed-loss','exec'),ns)
    n=5;pos=torch.randn(n,5,3);ang=torch.zeros(n,5,3);ang[:,:,2]=2
    vel=torch.cross(ang,pos,dim=-1)+torch.tensor([3.,2.,1.])
    e=SimpleNamespace(_perturb_cfg={'extremity_speed_loss_weight':2.},_extremity_speed_ids=torch.arange(5),
        _extremity_speed_limits=torch.ones(n,4),_motion_ids=torch.arange(n),
        _perturbed_rows=torch.tensor([1,1,1,0,1],dtype=torch.bool),_recovery_rows=torch.tensor([0,0,0,0,1],dtype=torch.bool))
    terms=torch.ones(n,7);call=lambda:ns['_append_extremity_speed_loss'](e,terms,pos,vel,ang)
    torch.testing.assert_close(call()[:,-1],torch.zeros(n))
    # One limb 1m/s over: mean(1,0,0,0)*2=.5; normals/get-ups stay zero.
    vel[:,1,0]+=2
    torch.testing.assert_close(call()[:,-1],torch.tensor([.5,.5,.5,0,0]))
    torch.testing.assert_close(call()[:,:-1],terms)
    e._perturb_cfg['extremity_speed_loss_weight']=0.;torch.testing.assert_close(call(),terms)
    done=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_update_done')
    gate=next(n for n in done.body if isinstance(n,ast.If) and any(isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and c.func.attr=='_extremity_speed_failure' for c in ast.walk(n)))
    hit=[];e._extremity_speed_enabled=True;e._extremity_speed_failure=lambda:hit.append(True) or torch.ones(n,dtype=torch.bool)
    e._perturb_cfg['extremity_speed_termination']=False
    ns.update(self=e,failed=torch.zeros(n,dtype=torch.bool))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[gate],type_ignores=[])),'actual-termination-gate','exec'),ns)
    assert not hit and not ns['failed'].any()
    return dict(passed=True,checks=['rigid pelvis motion excluded','squared excess and fixed scale','other losses unchanged','normal/recovery exclusions','disabled default','speed failure not called'])
