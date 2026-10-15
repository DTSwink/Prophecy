"""CPU preflight of the production opt-in, using the frozen Run LR checkpoint."""
import importlib.util, json
from pathlib import Path
import probe
import numpy as np
import torch
import yaml
import omni_walk

spec=importlib.util.spec_from_file_location('current_uefn_engine',probe.ROOT/'Labs/MimicKitTraining/uefn_engine.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class ZeroEngine(module.UefnNewtonEngine):
    def __init__(self,config,*args,**kwargs):
        config=dict(config,uefn_zero_joint_armature=True)
        super().__init__(config,*args,**kwargs)
omni_walk.UefnNewtonEngine=ZeroEngine
env,agent=probe.setup()
e=env._engine
assert not np.any(e._sim_model.joint_armature.numpy())
assert not np.any(e._solver.mj_model.dof_armature)
assert not np.any(e._solver.mjw_model.dof_armature.numpy())
# Engine construction already asserts the original mass, COM and inertia per body.
obs,info=env.reset()
for tick in range(32):
    with torch.no_grad(): action,_=agent._decide_action(obs,info)
    obs,reward,done,info=env.step(action)
    assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
    if done[0]: obs,info=env.reset()
report=dict(passed=True,ticks=32,armature_nonzero=0,bodies=e._sim_model.body_count,
            observations=obs.shape[-1],actions=action.shape[-1],mass_com_inertia_verified=True)
(probe.OUT/'production_zero_armature_preflight.json').write_text(json.dumps(report,indent=2))
print('PREFLIGHT',json.dumps(report))
