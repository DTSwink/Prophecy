"""Overlay only requested leg reversal and pushed-idle allocation changes."""
import copy,hashlib,json,zipfile
from pathlib import Path
import yaml
from prepare_leg_losses_20261028 import ROOT,OUT

def main():
    plan=json.loads((OUT/'previous-plan.json').read_text());cal=json.loads((OUT/'calibration.json').read_text());ref=json.loads((OUT/'reference.json').read_text())
    changed={}
    with zipfile.ZipFile(plan['source']['local']) as old:
        def read(n):return old.read('pipeline/'+n).decode().replace('\r\n','\n')
        def put(n,s):compile(s,n,'exec');changed['pipeline/'+n]=s.encode()
        def one(s,a,b):assert s.count(a)==1,(a,s.count(a));return s.replace(a,b,1)
        s=read('omni_walk.py')
        s='from idle_minus_allocation import idle_layout\n'+s
        s=one(s,"float(config['idle_row_fraction']), self.get_num_envs())", "idle_layout(config, self.get_num_envs())[0]/self.get_num_envs(), self.get_num_envs())")
        put('omni_walk.py',s)
        s=read('perturbed_omni.py');s='from idle_minus_allocation import idle_layout\nfrom leg_reversal import LegReversal\n'+s
        s=one(s,"        normal_idle = round(normal*float(config['idle_row_fraction']))", "        _, normal_idle, _ = idle_layout(config, n)\n        normal = normal_idle + round((n-self._idle_rows)*(1-float(cfg['fraction'])))")
        # Persist desired pushed-idle count before FinalLocomotion builds its masks.
        s=one(s,'        self._perturbed_ids = torch.where(self._perturbed_rows)[0]', '        self._idle_minus_count = idle_layout(config, n)[2]\n        self._perturbed_ids = torch.where(self._perturbed_rows)[0]')
        anchor="        self.loss_weights['head_reversal'] = float(cfg['head_reversal_other_weight'])"
        s=one(s,anchor,anchor+'''
        leg_cfg = cfg['leg_reversal']
        self._leg_ids = torch.tensor([names.index(b) for b in leg_cfg['bones']], device=self._device)
        self._leg_reversal = LegReversal(n, self._device)
        self._leg_weights = torch.tensor(leg_cfg['weights'], device=self._device)
        self._leg_allowance = torch.tensor([leg_cfg['motions'][name] for name in foot_names], device=self._device)
        self.loss_term_names = (*self.loss_term_names, 'leg_reversal')
        self.loss_weights['leg_reversal'] = 1.
''')
        anchor='        self._foot_regularizers.reset(env_ids, feet_pos, feet_rot, feet_bottoms)'
        s=one(s,anchor,anchor+"\n        self._leg_reversal.reset(env_ids, self._engine.get_body_pos(char)[env_ids][:, self._leg_ids], self._engine.get_body_rot(char)[env_ids][:, self._leg_ids])")
        s=one(s,'        return torch.cat((terms, foot_terms), -1)', '''        leg_raw = self._leg_reversal.append(pos[:, self._leg_ids], rot[:, self._leg_ids])
        leg_cost = ((leg_raw-self._leg_allowance[self._motion_ids]).clamp_min(0)*self._leg_weights).sum(-1)
        return torch.cat((terms, foot_terms, leg_cost[:, None]), -1)''')
        anchor="        result['foot_regularizers'] = self._perturb_cfg['foot_regularizers']['description']"
        s=one(s,anchor,anchor+"\n        result['leg_reversal'] = self._perturb_cfg['leg_reversal']['description']")
        put('perturbed_omni.py',s)
        s=read('final_locomotion.py');s=one(s,'round(len(idle)*.5),n,dev)',"getattr(env, '_idle_minus_count', round(len(idle)*.5)),n,dev)");put('final_locomotion.py',s)
        s=read('lossless_runtime.py');a='            buffers.extend(getattr(e._foot_regularizers,n) for n in e._foot_regularizers.buffer_names)';s=one(s,a,a+'\n            buffers.extend(getattr(e._leg_reversal,n) for n in e._leg_reversal.buffer_names)');put('lossless_runtime.py',s)
        for n in ['leg_reversal.py','idle_minus_allocation.py']:put(n,Path(__file__).with_name(n).read_text())
        cfg=yaml.safe_load(old.read('prepared/env_config.yaml'));cfg['perturbed_motion']['idle_minus_min_fraction']=.03
        cfg['perturbed_motion']['leg_reversal']=dict(bones=cal['bones'],weights=cal['weights'],motions=ref,description=cal['method'])
        changed['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
        source=OUT/'source.zip'
        with zipfile.ZipFile(source,'w') as z:
            for info in old.infolist():z.writestr(copy.copy(info),changed.get(info.filename,old.read(info.filename)))
            for n in set(changed)-set(old.namelist()):z.writestr(n,changed[n])
        with zipfile.ZipFile(OUT/'overlay.zip','w',zipfile.ZIP_DEFLATED) as z:
            for n,data in changed.items():z.writestr(n,data)
        for n,data in changed.items():
            p=OUT/'candidate'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest();plan.update(source=dict(local=str(source),key='mimickit/pipeline_20261014/leg-losses/source_'+sha[:12]+'.zip',sha256=sha),run_suffix='uefn_locomotion_leg7_idle3_2048')
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2));print(json.dumps(dict(source=plan['source'],changed=list(changed),calibration=cal['calibrated_share'])),flush=True)

if __name__=='__main__':main()
