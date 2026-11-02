"""Build isolated pinned-source candidate; never stop or launch training."""
import copy,hashlib,json,sys,zipfile,pickle
from pathlib import Path
import yaml
from prepare_head_reversal_20261025 import ROOT,OUT

def one(s,old,new):
    assert s.count(old)==1,(s.count(old),old[:110])
    return s.replace(old,new,1)

def build(mode):
    assert mode in ('either','both')
    plan=json.loads((ROOT/'Saved/MimicKitLocomotion/getup-success-prepared.json').read_text())
    previous=plan['source']; assert previous['sha256']=='f83f9855bce340e4ce33a8c71103c3d61491316fce5f71ac017069a889b67d72'
    assert hashlib.sha256(Path(previous['local']).read_bytes()).hexdigest()==previous['sha256']
    calibration=json.loads((OUT/'calibration.json').read_text());weights=calibration['weights']
    with zipfile.ZipFile(previous['local']) as old:
        changed={}
        s=old.read('pipeline/perturbed_omni.py').decode().replace('\r\n','\n')
        s=one(s,'\nimport torch\n','\nimport torch\nfrom head_reversal import HeadReversal\nfrom com2_reward_gate import com2_reward_gate\n')
        s=one(s,'        self.loss_terms = torch.zeros((n, len(self.loss_term_names)), device=self._device)', '''        self._head_reversal = HeadReversal(n, self._device)
        self._head_reversal_weights = torch.where(self._gaits == -1,
            float(cfg['head_reversal_idle_weight']), float(cfg['head_reversal_other_weight']))
        self.loss_term_names = (*self.loss_term_names, 'head_reversal')
        self.loss_weights['head_reversal'] = float(cfg['head_reversal_other_weight'])
        self._com2_reward_values = torch.zeros((n, 3), device=self._device)
        self._com2_reward_values[:, 0] = 1.
        self._com2_gate_diagnostics = torch.zeros(2, device=self._device)
        self.loss_terms = torch.zeros((n, len(self.loss_term_names)), device=self._device)''')
        s=one(s,'        self._prior_raw[env_ids] = 0.', '''        self._head_reversal.reset(env_ids,
            self._engine.get_body_pos(char)[env_ids, self._head_id] - self._engine.get_body_pos(char)[env_ids, 0])
        self._com2_reward_values[env_ids] = 0.
        self._com2_reward_values[env_ids, 0] = 1.
        self._prior_raw[env_ids] = 0.''')
        s=one(s,'        return terms\n\n    def _base_perturbed_tracking_losses', '''        raw = self._head_reversal.append(pos[:, self._head_id]-pos[:, 0])
        cost = raw*self._head_reversal_weights[self._motion_ids]
        return torch.cat((terms, cost[:, None]), -1)

    def _base_perturbed_tracking_losses''')
        s=one(s,'    def _update_reward(self):\n        super()._update_reward()', '''    def _update_reward(self):
        super()._update_reward()
        if self._perturb_ready:
            motion = self._motion_ids
            velocity = com2_velocity(self._engine.get_body_vel(self._get_char_id())[:, self._com2_ids], self._com2_masses)
            factor, distance, angle = com2_reward_gate(velocity, self._com2_targets[motion],
                self._com2_loss_basis[motion], self._com2_loss_leeway[motion], self._gaits[motion] == -1,
                self._perturb_cfg['com2_reward_require_both'])
            self._com2_reward_values.copy_(torch.stack((factor, distance, angle), -1))
            # Failure penalties are applied later in _update_done and must NOT be attenuated.
            self._reward_buf.mul_(factor)
            if self._mode == EnvMode.TRAIN:
                self._com2_gate_diagnostics[0].add_(factor.sum())
                self._com2_gate_diagnostics[1].add_(self.get_num_envs())''')
        s=one(s,'        return dict(getup_head_height=head/count, total=total/all_count) if count and all_count else {}', '''        result = dict(getup_head_height=head/count, total=total/all_count) if count and all_count else {}
        factor, rows = self._com2_gate_diagnostics.cpu().tolist()
        self._com2_gate_diagnostics.zero_()
        if rows: result['com2_multiplier'] = factor/rows
        return result''')
        s=one(s,'        result = super().recovery_row_metadata(world)', '''        result = super().recovery_row_metadata(world)
        result['head_reversal_weight'] = float(self._head_reversal_weights[self._motion_ids[world]])
        result['head_reversal_definition'] = 'Causal body-origin head minus pelvis translation; trailing2 interval mean, 0.02m/s deadzone, mean opposing dot product over6 previous ticks; first8 ticks zero; all rows/all handoff stages'
        result['com2_reward_gate'] = dict(distance_thresholds_m_s=[1., 2.], angle_thresholds_deg=[40., 60.],
            minimum=.001, require_both=self._perturb_cfg['com2_reward_require_both'], idle_direction=False,
            interpolation='smoothstep', active='all rows/all ticks; terminal penalty unscaled',
            distance='Euclidean distance to nearest point of existing COM2 directional bounds')''')
        changed['pipeline/perturbed_omni.py']=s.encode()
        s=old.read('pipeline/lossless_runtime.py').decode().replace('\r\n','\n')
        s=one(s,"'_tracking_mix','_ae_diagnostics','_head_height_reward','_reward_diagnostics']", "'_tracking_mix','_ae_diagnostics','_head_height_reward','_reward_diagnostics',\n    '_com2_reward_values','_com2_gate_diagnostics']")
        s=one(s,"            buffers.extend(getattr(e._prior,n) for n in ['positions','rotations','valid'])", "            buffers.extend(getattr(e._prior,n) for n in ['positions','rotations','valid'])\n            buffers.extend(getattr(e._head_reversal,n) for n in e._head_reversal.buffer_names)")
        changed['pipeline/lossless_runtime.py']=s.encode()
        s=old.read('pipeline/observe.py').decode().replace('\r\n','\n')
        s=one(s,'        original_step=env.step', "        self.com2_reward_values=torch.empty((self.capacity,3),device=env._device) if hasattr(env,'_com2_reward_values') else None\n        original_step=env.step")
        s=one(s,'        self.data[i,2].copy_(self.env._reward_buf[self.world])', '        self.data[i,2].copy_(self.env._reward_buf[self.world])\n        if self.com2_reward_values is not None:self.com2_reward_values[i].copy_(self.env._com2_reward_values[self.world])')
        s=one(s,'        if getattr(self.env, \'_additive_head_reward\', False):', '''        if self.com2_reward_values is not None:
            gate=self.com2_reward_values[:n].cpu().numpy()
            metadata.update(frame_com2_reward_multiplier=gate[:,0].tolist(),
                frame_com2_bound_distance=gate[:,1].tolist(),frame_com2_direction_degrees=gate[:,2].tolist(),
                frame_rewards=data[:,2].tolist())
        if getattr(self.env, '_additive_head_reward', False):''')
        changed['pipeline/observe.py']=s.encode()
        s=old.read('pipeline/observe_many.py').decode().replace('\r\n','\n')
        assert s.count("'phase_values','prior_values')")==2
        s=s.replace("'phase_values','prior_values')", "'phase_values','prior_values','com2_reward_values')")
        s=one(s,'        self.data[i,:,2].copy_(self.env._reward_buf[ids])', '        self.data[i,:,2].copy_(self.env._reward_buf[ids])\n        if self.com2_reward_values is not None:self.com2_reward_values[i].copy_(self.env._com2_reward_values[ids])')
        changed['pipeline/observe_many.py']=s.encode()
        for name in ['head_reversal.py','com2_reward_gate.py']:changed['pipeline/'+name]=Path(__file__).with_name(name).read_bytes()
        cfg=yaml.safe_load(old.read('prepared/env_config.yaml'));before=copy.deepcopy(cfg)
        cfg['perturbed_motion'].update(head_reversal_idle_weight=weights['idle'],head_reversal_other_weight=weights['other'],com2_reward_require_both=mode=='both')
        changed['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
        for name,data in changed.items():
            p=OUT/'candidate'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            if name.endswith('.py'):compile(data,name,'exec')
        source=OUT/'source-stored.zip'
        with zipfile.ZipFile(source,'w') as dst:
            for info in old.infolist():dst.writestr(copy.copy(info),changed.get(info.filename,old.read(info.filename)))
            for name in sorted(set(changed)-set(old.namelist())):dst.writestr(name,changed[name])
        with zipfile.ZipFile(source) as new:
            assert new.testzip() is None
            actual=[n for n in new.namelist() if n not in old.namelist() or new.read(n)!=old.read(n)]
            assert set(actual)==set(changed)
            with zipfile.ZipFile(OUT/'overlay.zip','w',zipfile.ZIP_DEFLATED) as overlay:
                overlay.writestr('infos.pkl',pickle.dumps(new.infolist(),protocol=4))
                for name,data in changed.items():overlay.writestr(name,data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    plan.update(source=dict(local=str(source),key='mimickit/pipeline_20261014/head-reversal-com2/source_'+sha[:12]+'.zip',sha256=sha),run_suffix='uefn_locomotion_head_com2_2048')
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2));(OUT/'previous-plan.json').write_text(json.dumps(dict(previous_source=previous),indent=2))
    (OUT/'source-checks.json').write_text(json.dumps(dict(mode=mode,changed=actual,sha256=sha),indent=2))
    print(json.dumps(dict(mode=mode,source_sha=sha,changed=actual)))

if __name__=='__main__':build(sys.argv[1])
