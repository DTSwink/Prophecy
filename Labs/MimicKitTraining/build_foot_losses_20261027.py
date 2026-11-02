"""Build isolated pinned-source overlay for the three requested foot losses."""
import copy, hashlib, json, pickle, zipfile
from pathlib import Path
import yaml
from prepare_foot_losses_20261027 import ROOT,OUT


def one(s,old,new):
    assert s.count(old)==1,(s.count(old),old[:80])
    return s.replace(old,new,1)


def main():
    plan=json.loads((ROOT/'Saved/MimicKitLocomotion/getup-success-prepared.json').read_text())
    prev=plan['source'];assert hashlib.sha256(Path(prev['local']).read_bytes()).hexdigest()==prev['sha256']
    assert prev['sha256'].startswith('853a1f6c0661')
    ref=json.loads((OUT/'cadence-reference.json').read_text());cal=json.loads((OUT/'calibration.json').read_text())
    with zipfile.ZipFile(prev['local']) as old:
        s=old.read('pipeline/perturbed_omni.py').decode().replace('\r\n','\n')
        s=one(s,'from head_reversal import HeadReversal','from head_reversal import HeadReversal\nfrom foot_regularizers import FootRegularizers')
        s=one(s,'        self._head_reversal = HeadReversal(n, self._device)', '''        self._foot_regularizers = FootRegularizers(n, self._device)
        foot_cfg = cfg['foot_regularizers']
        self._foot_loss_weights = torch.tensor(foot_cfg['weights'], device=self._device)
        foot_reference = foot_cfg['motions']
        foot_names = [Path(self._motion_lib.get_motion_file(i)).stem for i in range(self._motion_lib.get_num_motions())]
        self._foot_periods = torch.tensor([foot_reference[name]['period_ticks'] for name in foot_names], device=self._device)
        self._foot_reversal_allowance = torch.tensor([foot_reference[name]['reversal_allowance'] for name in foot_names], device=self._device)
        for name, weight in zip(foot_cfg['terms'], foot_cfg['weights']):
            self.loss_term_names = (*self.loss_term_names, name)
            self.loss_weights[name] = weight
        self._head_reversal = HeadReversal(n, self._device)''')
        # Names must match actual appended order: head then the three foot terms.
        s=one(s,"        self.loss_term_names = (*self.loss_term_names, 'head_reversal')", "        self.loss_term_names = (*self.loss_term_names[:-3], 'head_reversal', *self.loss_term_names[-3:])")
        s=one(s,'        self._head_reversal.reset(env_ids,', '''        feet_pos = self._engine.get_body_pos(char)[env_ids][:, self._walking_foot_ids]
        feet_rot = self._engine.get_body_rot(char)[env_ids][:, self._walking_foot_ids]
        feet_bottoms = foot_box_bottoms(feet_pos, feet_rot, self._walking_foot_centers, self._walking_foot_half_axes)
        self._foot_regularizers.reset(env_ids, feet_pos, feet_rot, feet_bottoms)
        self._head_reversal.reset(env_ids,''')
        s=one(s,'        return torch.cat((terms, cost[:, None]), -1)\n\n    def _base_perturbed_tracking_losses', '''        terms = torch.cat((terms, cost[:, None]), -1)
        ids = self._walking_foot_ids
        bottoms = foot_box_bottoms(pos[:, ids], rot[:, ids], self._walking_foot_centers, self._walking_foot_half_axes)
        raw = self._foot_regularizers.append(pos[:, ids], rot[:, ids], bottoms, self._foot_periods[self._motion_ids])
        reversals = (raw[:, 1:]-self._foot_reversal_allowance[self._motion_ids]).clamp_min(0.)
        # Exactly the same fade as AE, including the repeated P-minus idle handoff.
        foot_terms = torch.cat((raw[:, :1]*(1-self._tracking_mix[:, None]), reversals), -1)*self._foot_loss_weights
        return torch.cat((terms, foot_terms), -1)

    def _base_perturbed_tracking_losses''')
        s=one(s,"        result['head_reversal_weight'] =", "        result['foot_regularizers'] = self._perturb_cfg['foot_regularizers']['description']\n        result['foot_minimum_period_ticks'] = self._foot_periods[self._motion_ids[world]].cpu().tolist()\n        result['foot_reversal_allowance'] = self._foot_reversal_allowance[self._motion_ids[world]].cpu().tolist()\n        result['head_reversal_weight'] =")
        changed={'pipeline/perturbed_omni.py':s.encode(),'pipeline/foot_regularizers.py':Path(__file__).with_name('foot_regularizers.py').read_bytes()}
        s=old.read('pipeline/lossless_runtime.py').decode().replace('\r\n','\n')
        anchor='            buffers.extend(getattr(e._head_reversal,n) for n in e._head_reversal.buffer_names)'
        s=one(s,anchor,anchor+'\n            buffers.extend(getattr(e._foot_regularizers,n) for n in e._foot_regularizers.buffer_names)')
        changed['pipeline/lossless_runtime.py']=s.encode()
        cfg=yaml.safe_load(old.read('prepared/env_config.yaml'))
        cfg['perturbed_motion']['foot_regularizers']=dict(weights=cal['weights'],terms=cal['terms'],motions=ref['motions'],
            description='World-space foot translation/rotation reversals: trailing2 mean,6-tick opposing velocity history, deadzones0.02m/s and0.1rad/s, first8ticks zero; authored per-motion max allowance. Always on all rows. Excess stepping:1/2.5cm collider hysteresis, repeated per-foot liftoff faster than authored cadence minus10% tolerance, dense decay; multiplied by1-tracking_mix. Fixed calibrated15/10/5% coefficients.')
        changed['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
        for name,data in changed.items():
            p=OUT/'candidate'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            if name.endswith('.py'):compile(data,name,'exec')
        source=OUT/'source-stored.zip'
        with zipfile.ZipFile(source,'w') as z:
            for info in old.infolist():z.writestr(copy.copy(info),changed.get(info.filename,old.read(info.filename)))
            for name in sorted(set(changed)-set(old.namelist())):z.writestr(name,changed[name])
        with zipfile.ZipFile(source) as new:
            assert new.testzip() is None
            actual=[n for n in new.namelist() if n not in old.namelist() or old.read(n)!=new.read(n)]
            assert set(actual)==set(changed)
            with zipfile.ZipFile(OUT/'overlay.zip','w',zipfile.ZIP_DEFLATED) as delta:
                delta.writestr('infos.pkl',pickle.dumps(new.infolist(),protocol=4))
                for name,data in changed.items():delta.writestr(name,data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    plan.update(source=dict(local=str(source),key='mimickit/pipeline_20261014/foot-losses/source_'+sha[:12]+'.zip',sha256=sha),run_suffix='uefn_locomotion_foot_losses_2048',worlds=2048)
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2));(OUT/'previous-plan.json').write_text(json.dumps(dict(previous_source=prev),indent=2))
    print(json.dumps(dict(sha256=sha,changed=actual,weights=cal['weights'])),flush=True)


if __name__=='__main__':main()
