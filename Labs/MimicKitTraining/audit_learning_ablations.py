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
if 'actor_lr' in plan:
    override_actor_learning_rate(agent,plan['actor_lr'])
with torch.no_grad():agent._model._action_dist._logstd_net.fill_(np.log(variant['noise']))
result=dict(variant=variant,checkpoint=plan['checkpoint'],sha256=plan['sha256'],
            reward_config=cfg['perturbed_motion'],
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

updates=variant['equivalent_updates']*32//variant['ticks']
evaluation_updates=variant.get('evaluate_at_updates',[updates])
snapshots={}
if plan.get('require_success_fix') and (cfg['perturbed_motion'].get('getup_success_value')!=100 or cfg['perturbed_motion'].get('getup_success_discount')!=.99):
    raise RuntimeError('Comparison requires the live success reward fix')
if updates:
    agent._curr_obs,agent._curr_info=reset(variant.get('seed',13579),AgentMode.TRAIN)
    result['training_initial_observation_sha256']=digest(agent._curr_obs)
    result['actual_noise']=agent._model._action_dist._logstd_net.exp().detach().cpu().tolist()
    for index in range(updates):
        agent._iter=index;t=time.perf_counter()
        info=agent._train_iter();torch.cuda.synchronize()
        agent._sample_count=agent._update_sample_count()
        result['updates'].append(dict(update=index+1,seconds=time.perf_counter()-t,
            metrics={k:float(v) for k,v in info.items()},outcomes=env.take_training_outcomes()))
        if index+1 in evaluation_updates:
            snapshots[index+1]={k:v.detach().cpu().clone() for k,v in agent.state_dict().items()}
        save()
else:
    agent._curr_obs,agent._curr_info=reset(13579,AgentMode.TRAIN)
    with torch.no_grad():agent._rollout_train(32)
    result['untrained_warmup_ticks']=32;save()
    snapshots[0]={k:v.detach().cpu().clone() for k,v in agent.state_dict().items()}
result['training_seconds']=sum(x['seconds'] for x in result['updates'])
result['training_transitions']=updates*variant['ticks']*512
# All candidates evaluated on the original uniform strengths, never their own
# training distribution. TEST actions have no exploration noise.
env._getup_upper_half_probability=.5
# Held-out starts, shared by baseline and all candidate policies. One episode
# per get-up row, so fast successes cannot crowd out difficult starts.
for evaluation_update in evaluation_updates:
    agent.load_state_dict(snapshots[evaluation_update])
    for seed in [83191,83192,83193,83194]:
        obs,info=reset(seed,AgentMode.TEST)
        ids=torch.arange(512,device='cuda');getup=env._perturbed_getup.clone()
        group=torch.where(getup,2,torch.where(env._perturbed_rows & ~env._recovery_rows & (env._gaits[env._motion_ids]!=-1),1,0))
        alpha=env._pose_blend[ids].clone();side=env._recovery_motion[ids].clone()
        gait=env._gaits[env._motion_ids[ids]].clone()
        recovery=env._recovery_rows[ids].clone();perturbed=env._perturbed_rows[ids].clone()
        initial_obs=obs[ids].clone();initial_pos=env._engine.get_body_pos(0)[ids].clone()
        initial_vel=env._engine.get_body_vel(0)[ids].clone()
        initial_qd=wp.to_torch(env._engine._sim_state.raw_state.joint_qd).view(512,-1).clone()
        active=torch.ones(len(ids),device='cuda',dtype=torch.bool)
        reasons=torch.zeros(len(ids),device='cuda',dtype=torch.long)
        done_end=torch.zeros_like(reasons);ends=torch.zeros_like(reasons);reward_sum=torch.zeros(len(ids),device='cuda')
        end_head=torch.zeros_like(reward_sum);end_cost=torch.zeros_like(reward_sum)
        with torch.no_grad():
            for tick in range(300):
                action,_=agent._decide_action(obs,info)
                obs,reward,done,info=env.step(action)
                reward_sum+=torch.where(active,reward[ids],0)
                finishing=active & (done[ids]!=0)
                reasons[finishing]=env._reset_reason[ids][finishing]
                ends[finishing]=tick+1;done_end[finishing]=done[ids][finishing].long()
                head=env._engine.get_body_pos(0)[ids,env._head_id,2]/env._idle_head_height[env._motion_ids[ids]]
                end_head[finishing]=head[finishing];end_cost[finishing]=env.loss_terms[ids,0][finishing]
                active &= ~finishing
                if not active.any():break
                obs,info=agent._reset_done_envs(done)
        entry=dict(evaluation_update=evaluation_update,seed=seed,initial_observation_sha256=digest(initial_obs),
            initial_position_sha256=digest(initial_pos),initial_velocity_sha256=digest(initial_vel),
            getup_observation_sha256=digest(initial_obs[getup]),getup_velocity_sha256=digest(initial_vel[getup]),
            initial_observation=initial_obs.cpu().tolist(),initial_velocity=initial_vel.cpu().tolist(),
            rows=len(ids),unfinished=int(active.sum()),group=group.cpu().tolist(),
            gait=gait.cpu().tolist(),recovery=recovery.cpu().tolist(),perturbed=perturbed.cpu().tolist(),
            final_done=done_end.cpu().tolist(),
            row_ids=ids.cpu().tolist(),alpha=alpha.cpu().tolist(),side=side.cpu().tolist(),
            reasons=reasons.cpu().tolist(),end_ticks=ends.cpu().tolist(),
            end_head_ratio=end_head.cpu().tolist(),end_position_cost=end_cost.cpu().tolist(),
            episode_return=reward_sum.cpu().tolist())
        result['evaluations'].append(entry);save()
result['complete']=True;save();print('LEARNING_ABLATION_COMPLETE',args.variant,flush=True)
