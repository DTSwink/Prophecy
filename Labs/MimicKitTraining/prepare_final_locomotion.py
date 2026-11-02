"""Build an isolated final-phase source package from the stopped checkpoint."""
import ast,hashlib,json,zipfile
from pathlib import Path
import numpy as np
import yaml
import deploy_locomotion_branch as d

def once(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)

def patch(s):
    s=once(s,'        self._perturb_ready = True\n',"        self._perturb_ready = True\n        if cfg.get('final_phase'):\n            from final_locomotion import FinalLocomotion\n            self._final = FinalLocomotion(self, cfg['final_phase'])\n")
    anchor='        ids = env_ids[self._perturbed_rows[env_ids] & ~self._recovery_rows[env_ids]]\n        motion = self._motion_ids[ids]'
    s=once(s,anchor,"        if hasattr(self, '_final'):\n            self._final.reference(env_ids)\n"+anchor)
    anchor='        self._reset_floor_lift[env_ids] = 0.\n'
    s=once(s,anchor,anchor+"        if hasattr(self, '_final'):\n            self._final.reset_state(env_ids)\n            return\n")
    s=once(s,'    def step(self, action):\n',"    def step(self, action):\n        if hasattr(self, '_final'):\n            self._final.before_step()\n")
    anchor="        failed &= (self._gaits[self._motion_ids] != -1) & (ticks > self._perturb_cfg['grace_ticks'])\n"
    s=once(s,anchor,anchor+"        if hasattr(self, '_final'):\n            failed &= self._final.velocity_gate(ticks)\n")
    tree=ast.parse(s);method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='recovery_row_metadata')
    lines=s.splitlines(True);part=''.join(lines[method.lineno-1:method.end_lineno])
    part=part.replace('return result',"return self._final.metadata(world, result) if hasattr(self, '_final') else result")
    s=''.join(lines[:method.lineno-1])+part+''.join(lines[method.end_lineno:]);compile(s,'patched','exec')
    return s

def main():
    baseline=d.OUT/'final-phase-before-plan.json'
    old=json.loads((baseline if baseline.exists() else d.OUT/'getup-success-prepared.json').read_text())
    if not baseline.exists():d.save('final-phase-before-plan',old)
    bank=d.OUT/'final-phase-inits/initializations.npz'
    with np.load(bank,allow_pickle=False) as z:arrays={n:z[n] for n in z.files}
    rng=np.random.default_rng(2026102380);a=rng.uniform(-np.pi,np.pi,(8192,10,5));strength=rng.uniform(0,3,(8192,10,5))
    arrays['kicks']=np.stack((np.cos(a)*strength,np.sin(a)*strength),-1).astype(np.float32)
    np.savez_compressed(bank,**arrays);sha=hashlib.sha256(bank.read_bytes()).hexdigest()
    with zipfile.ZipFile(old['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    entries['pipeline/perturbed_omni.py']=patch(entries['pipeline/perturbed_omni.py'].decode()).encode()
    omni=entries['pipeline/omni_walk.py'].decode()
    anchor='        self._done_buf[failed]=DoneFlags.FAIL.value\n'
    omni=once(omni,anchor,"        if hasattr(self, '_final'):\n            failed &= ~self._final.minus\n"+anchor)
    entries['pipeline/omni_walk.py']=omni.encode()
    entries['pipeline/final_locomotion.py']=Path(__file__).with_name('final_locomotion.py').read_bytes()
    observe=entries['pipeline/observe_many.py'].decode()
    observe=once(observe,'        self.selection_round+=1\n',"        if hasattr(self.env, '_final'):\n            selected=self.env._final.replay_worlds(selected,self.selection_round)\n        self.selection_round+=1\n")
    entries['pipeline/observe_many.py']=observe.encode()
    entries['prepared/final_initializations.npz']=bank.read_bytes()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml']);cfg['perturbed_motion']['episode_ticks']=150
    cfg['perturbed_motion']['final_phase']=dict(initializations='/workspace/mimickit_trial/prepared/final_initializations.npz',sha256=sha,
        pushed_fraction=.3,plus_fraction=.7,push_tick=80,velocity_restore_tick=130,plus_foot_grace=40,minus_idle_fraction=.5,minus_kick_interval=30)
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    source=d.OUT/'final-locomotion-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for n,data in entries.items():z.writestr(n,data)
    data=source.read_bytes();digest=hashlib.sha256(data).hexdigest();key='mimickit/pipeline_20261014/final-locomotion/source_'+digest[:12]+'.zip'
    plan=dict(old,source=dict(local=str(source),key=key,sha256=digest),run_suffix='uefn_locomotion_final_push_plus_1024')
    d.save('final-phase-prepared',plan)
    report=dict(bank_sha256=sha,bank_bytes=bank.stat().st_size,source_bytes=len(data),push_starts=len(arrays['push_dof'])*arrays['push_dof'].shape[1],plus_starts=len(arrays['plus_dof']),push_plans=len(arrays['kicks']),cp=plan['checkpoint']['key'])
    d.save('final-phase-package',report);print(json.dumps(report),flush=True)

if __name__=='__main__':main()
