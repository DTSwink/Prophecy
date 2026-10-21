"""Factorial exploration/credit-assignment audit on disposable learners only."""
import argparse,hashlib,json,random,sys,time
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import numpy as np,torch,warp as wp,mujoco_warp as mjw,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore,override_actor_learning_rate

parser=argparse.ArgumentParser()
parser.add_argument('directory');parser.add_argument('variant')
args=parser.parse_args();out=Path(args.directory);plan=json.loads((out/'plan.json').read_text())
variant=plan['variants'][args.variant]
started=time.time()
torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6793)
run=ROOT/'runs'/plan['run']
cfg,ec,ac=[yaml.safe_load((run/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
cfg['perturbed_motion']['getup_upper_half_probability']=variant.get('upper_probability',2/3)
ac['steps_per_iter']=variant['ticks'];ac['td_lambda']=variant['lambda']
env=PerturbedOmniEnv(cfg,ec,512,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
checkpoint=out/'checkpoint.zip'
assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==plan['sha256']
restored=restore(agent,checkpoint);agent._init_train()
with torch.no_grad():agent._model._action_dist._logstd_net.fill_(np.log(variant['noise']))
result=dict(variant=variant,checkpoint=plan['checkpoint'],sha256=plan['sha256'],
            restored=restored,updates=[],evaluations=[],live_trainer_modified=False)
def save():
    result['elapsed_seconds']=time.time()-started
    dest=out/f'result_{args.variant}.json';tmp=dest.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,indent=2));tmp.replace(dest)
def reset(seed,mode):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    agent.eval();agent.set_mode(mode)
    solver=env._engine._solver
    mjw.reset_data(solver.mjw_model,solver.mjw_data)
    return agent._reset_envs()
def digest(tensor):
    return hashlib.sha256(tensor.detach().cpu().contiguous().numpy().tobytes()).hexdigest()


obs,info=reset(83191,AgentMode.TEST)
before=dict(obs=obs.clone(),velocity=env._engine.get_body_vel(0).clone(),qd=wp.to_torch(env._engine._sim_state.raw_state.joint_qd).view(512,-1).clone())
with torch.no_grad():
 for t in range(32):
  action,_=agent._decide_action(obs,info);obs,_,done,info=env.step(action);obs,info=agent._reset_done_envs(done)
obs,info=reset(83191,AgentMode.TEST)
after=dict(obs=obs.clone(),velocity=env._engine.get_body_vel(0).clone(),qd=wp.to_torch(env._engine._sim_state.raw_state.joint_qd).view(512,-1).clone())
report={}
for k in before:
 diff=(before[k]-after[k]).abs().reshape(512,-1)
 report[k]=dict(max=float(diff.max()),getup_max=float(diff[env._perturbed_getup].max()),other_max=float(diff[~env._perturbed_getup].max()),rows_over_1e6=int((diff.max(-1).values>1e-6).sum()),worst_indices=torch.topk(diff.max(0).values,5).indices.cpu().tolist())
(out/'reset-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
