"""Disposable full-PPO LR comparison. Never changes a live trainer or checkpoint."""
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
parser.add_argument('directory');parser.add_argument('multiplier',type=int,choices=[0,2,4,8])
parser.add_argument('--hold-rate',action='store_true',
                    help='Keep the requested LR between updates; retain KL rejection/rollback.')
args=parser.parse_args();out=Path(args.directory);plan=json.loads((out/'plan.json').read_text())
started=time.time()
torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6793)
run=ROOT/'runs'/plan['run']
cfg,ec,ac=[yaml.safe_load((run/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
env=PerturbedOmniEnv(cfg,ec,512,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
checkpoint=out/'checkpoint.zip'
assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==plan['sha256']
restored=restore(agent,checkpoint);agent._init_train()
result=dict(multiplier=args.multiplier,checkpoint=plan['checkpoint'],sha256=plan['sha256'],
            restored=restored,updates=[],evaluations=[],live_trainer_modified=False,
            hold_requested_rate=args.hold_rate)
def save():
    result['elapsed_seconds']=time.time()-started
    suffix='_fixed' if args.hold_rate else ''
    (out/f'result_{args.multiplier}{suffix}.json').write_text(json.dumps(result,indent=2))
def reset(seed,mode):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    agent.eval();agent.set_mode(mode)
    solver=env._engine._solver
    mjw.reset_data(solver.mjw_model,solver.mjw_data)
    return agent._reset_envs()
def digest(tensor):
    return hashlib.sha256(tensor.detach().cpu().contiguous().numpy().tobytes()).hexdigest()

if args.multiplier:
    result['lr_override']=override_actor_learning_rate(agent,plan['base_lr']*args.multiplier)
    agent._curr_obs,agent._curr_info=reset(13579,AgentMode.TRAIN)
    result['training_initial_observation_sha256']=digest(agent._curr_obs)
    for index in range(10):
        if args.hold_rate:
            override_actor_learning_rate(agent,plan['base_lr']*args.multiplier)
        agent._iter=index;t=time.perf_counter()
        info=agent._train_iter();torch.cuda.synchronize()
        agent._sample_count=agent._update_sample_count()
        result['updates'].append(dict(update=index+1,seconds=time.perf_counter()-t,
            metrics={k:float(v) for k,v in info.items()},outcomes=env.take_training_outcomes()))
        save()
else:
    save()

# Held-out starts, shared by baseline and all candidate policies. One episode
# per get-up row, so fast successes cannot crowd out difficult starts.
for seed in [83191,83192,83193,83194]:
    obs,info=reset(seed,AgentMode.TEST)
    ids=torch.where(env._perturbed_getup)[0]
    alpha=env._pose_blend[ids].clone();side=env._recovery_motion[ids].clone()
    initial_obs=obs[ids].clone();initial_pos=env._engine.get_body_pos(0)[ids].clone()
    initial_vel=env._engine.get_body_vel(0)[ids].clone()
    active=torch.ones(len(ids),device='cuda',dtype=torch.bool)
    reasons=torch.zeros(len(ids),device='cuda',dtype=torch.long)
    ends=torch.zeros_like(reasons);reward_sum=torch.zeros(len(ids),device='cuda')
    end_head=torch.zeros_like(reward_sum);end_cost=torch.zeros_like(reward_sum)
    with torch.no_grad():
        for tick in range(180):
            action,_=agent._decide_action(obs,info)
            obs,reward,done,info=env.step(action)
            reward_sum+=torch.where(active,reward[ids],0)
            finishing=active & (done[ids]!=0)
            reasons[finishing]=env._reset_reason[ids][finishing]
            ends[finishing]=tick+1
            head=env._engine.get_body_pos(0)[ids,env._head_id,2]/env._idle_head_height[env._motion_ids[ids]]
            end_head[finishing]=head[finishing];end_cost[finishing]=env.loss_terms[ids,0][finishing]
            active &= ~finishing
            if not active.any():break
            obs,info=agent._reset_done_envs(done)
    entry=dict(seed=seed,initial_observation_sha256=digest(initial_obs),
        initial_position_sha256=digest(initial_pos),initial_velocity_sha256=digest(initial_vel),
        rows=len(ids),unfinished=int(active.sum()),
        row_ids=ids.cpu().tolist(),alpha=alpha.cpu().tolist(),side=side.cpu().tolist(),
        reasons=reasons.cpu().tolist(),end_ticks=ends.cpu().tolist(),
        end_head_ratio=end_head.cpu().tolist(),end_position_cost=end_cost.cpu().tolist(),
        episode_return=reward_sum.cpu().tolist())
    result['evaluations'].append(entry);save()
result['complete']=True;save();print('TEN_UPDATE_TRIAL_COMPLETE',args.multiplier,flush=True)
