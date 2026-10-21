"""One discarded GPU update verifies correction before unchanged-checkpoint resume."""
import sys, json, time
from pathlib import Path
root=Path('/workspace/mimickit_trial')
sys.path.insert(0,str(root/'MimicKit/mimickit'))
import torch, warp as wp, yaml
from util import mp_util
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6794)
cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
env=PerturbedOmniEnv(cfg,ec,512,'cuda:0',False)
agent=OmniPPOAgent(ac,env,'cuda:0')
saved=restore(agent,root/'resume.zip')
agent._init_train();agent._curr_obs,agent._curr_info=agent._reset_envs()
ids=env._perturbed_getup
assert not env._recovery_start_frame[ids].any()
assert not env._recovery_start[ids].any()
assert not env._phase_supervision_mask[env._phase_feedback_ids].any()
assert abs(env._ae_weight-6.942658260262293)<1e-9
start=time.perf_counter();info=agent._train_iter();seconds=time.perf_counter()-start
assert torch.stack([p.isfinite().all() for p in agent.parameters()]).all()
assert not env.loss_terms[env._perturbed_rows,env.loss_term_names.index('flat_com_velocity')].any()
assert not agent._exp_buffer.get_data('phase_supervision')[:,env._phase_feedback_ids].any()
out=dict(passed=True,restored=saved,discarded_updates=1,seconds=seconds,
    getup_frame0=True,autoreg_phase_loss_mask_zero=True,perturbed_com_loss_zero=True,
    ae_weight=env._ae_weight,head_height_weight=env.loss_weights['getup_head_height'])
(root/'perturbed-correction-validation.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
