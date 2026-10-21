"""Bounded isolated frozen-checkpoint diagnosis. Never writes trainer state."""
import json, sys, time, hashlib
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import torch, numpy as np, warp as wp, yaml
from util import mp_util, torch_util as q
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore

OUT=ROOT/'head-learning-audit';OUT.mkdir(exist_ok=True)
start=time.time()
def save(value):
    (OUT/'result.json').write_text(json.dumps(value,indent=2));print(json.dumps(value),flush=True)
torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6797)
cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
env=PerturbedOmniEnv(cfg,ec,128,'cuda:0',False)
agent=OmniPPOAgent(ac,env,'cuda:0')
restored=restore(agent,OUT/'checkpoint.zip');agent._init_train();agent.eval()
result=dict(checkpoint=restored,worlds=128,live_trainer_modified=False,variants=[])
getup=env._perturbed_getup
def stats(x):
    x=x.detach().float().flatten();return dict(mean=float(x.mean()),min=float(x.min()),max=float(x.max())) if x.numel() else {}
def correlation(a,b):
    a=a.float().flatten();b=b.float().flatten();a=a-a.mean();b=b-b.mean()
    return float((a*b).sum()/(a.norm()*b.norm()).clamp_min(1e-12))

# One matched reset seed per variant. Only action sampling differs.
for label,sigma,hold in [('deterministic',0.,1),('training_noise',.05,1),('noise_x4',.2,1),('noise_x4_held8',.2,8)]:
    torch.manual_seed(7411);torch.cuda.manual_seed_all(7411)
    agent.set_mode(AgentMode.TEST)
    obs,info=agent._reset_envs()
    first=env._engine.get_body_pos(0)[:,env._head_id,2].clone()
    side=env._recovery_motion.clone();active=getup.clone();peak=first.clone()
    traces=[];noise=None;completed=torch.zeros_like(active)
    with torch.no_grad():
        for tick in range(180):
            norm=agent._obs_norm.normalize(obs);dist=agent._model.eval_actor(norm)
            if noise is None or tick%hold==0:noise=torch.randn_like(dist.mode)*sigma
            action=agent._a_norm.unnormalize(dist.mode+noise)
            env.queue_phase_prediction(agent._model.eval_phase(norm[env._phase_feedback_ids]))
            obs,reward,done,info=env.step(action)
            h=env._engine.get_body_pos(0)[:,env._head_id,2]
            peak=torch.where(active,torch.maximum(peak,h),peak)
            traces.append(torch.stack((h,env._head_height_reward,env._prior_raw*env._ae_weight,reward,active.float()),-1))
            completed|=active & (env._reset_reason==2)
            active &= done==0
            ids=torch.where(done!=0)[0]
            if len(ids):obs,info=agent._reset_envs(ids)
    data=torch.stack(traces)
    summaries=[]
    for side_id in [0,1]:
        ids=getup & (side==side_id);late=data[60:,ids];valid=late[:,:,4].bool()
        summaries.append(dict(side=side_id,rows=int(ids.sum()),head_peak=stats(peak[ids]),
            head_end=stats(data[-1,ids,0]),successes=int(completed[ids].sum()),
            late_head=stats(late[:,:,0][valid]),late_prior=stats(late[:,:,2][valid]),late_reward=stats(late[:,:,3][valid])))
    result['variants'].append(dict(name=label,sigma=sigma,hold_ticks=hold,sides=summaries))
    if label=='training_noise':
        result['action_noise_physical_rad_s']=stats(agent._a_norm._std*.05)
    save(result)

# Score the authored get-up sequences and static repetitions through the exact
# live encoder/scorer, without changing a physical world or its policy.
references=[]
with torch.no_grad():
    for motion in range(2):
        length=float(env._recovery_lib.get_motion_length(torch.tensor([motion],device='cuda'))[0])
        times=torch.arange(0,length,1/30,device='cuda');ids=torch.full_like(times,motion,dtype=torch.long)
        root,rot,_,_,joints,_=env._recovery_lib.calc_motion_frame(ids,times)
        pos,ori=env._kin_char_model.forward_kinematics(root,rot,joints);mat=q.quat_to_matrix(ori)
        pp=torch.stack([pos[:-2],pos[1:-1],pos[2:]],1);rr=torch.stack([mat[:-2],mat[1:-1],mat[2:]],1)
        prior=env._prior.scorer(env._prior.encode(pp,rr,ground_height=0.))*env._ae_weight
        frozenp=pos[2:,None].expand(-1,3,-1,-1);frozenr=mat[2:,None].expand(-1,3,-1,-1,-1)
        frozen=env._prior.scorer(env._prior.encode(frozenp,frozenr,ground_height=0.))*env._ae_weight
        target=env._idle_head_height[env._motion_ids[getup]][0];head=pos[2:,env._head_id,2]
        references.append(dict(motion=motion,frames=len(times),head=head.cpu().tolist(),
            prior=prior.cpu().tolist(),frozen_prior=frozen.cpu().tolist(),
            reward_if_height_active=(1/(1+prior)+(head/target).clamp(0,1)).cpu().tolist()))
result['authored_reference_scores']=references;save(result)

# Inspect on-policy advantages with frozen weights/critic, several contiguous
# 32-step buffers; no optimizer steps and no checkpoint writes.
torch.manual_seed(7411);torch.cuda.manual_seed_all(7411)
agent.set_mode(AgentMode.TRAIN);agent._curr_obs,agent._curr_info=agent._reset_envs()
original_step=agent._step_env;captures=[]
def step(action):
    before=env._engine.get_body_pos(0)[:,env._head_id,2].clone()
    age=env._time_buf.clone()*30
    out=original_step(action)
    after=env._engine.get_body_pos(0)[:,env._head_id,2].clone()
    captures.append(torch.stack((before,after,age,env._head_height_reward.clone()),-1))
    return out
agent._step_env=step
all_records=[];gradient_report=None
for batch in range(6):
    captures=[]
    with torch.no_grad():agent._rollout_train(32)
    agent._build_train_data()
    obs=agent._exp_buffer.get_data('obs');adv=agent._exp_buffer.get_data('adv');rew=agent._exp_buffer.get_data('reward')
    vals=agent._model.eval_critic(agent._obs_norm.normalize(obs)).squeeze(-1).detach()
    caps=torch.stack(captures)
    all_records.append(torch.cat((caps,adv[:,:,None],rew[:,:,None],vals[:,:,None]),-1).detach())
    if batch==3:
        flatobs=obs.flatten(0,1);flatadv=adv.flatten();actions=agent._exp_buffer.get_data('action').flatten(0,1)
        mask=getup.expand(32,-1).flatten();params=list(agent._model._actor_layers.parameters())
        gradients=[]
        for cohort in [mask,~mask]:
            dist=agent._model.eval_actor(agent._obs_norm.normalize(flatobs[cohort]))
            loss=-(flatadv[cohort]*dist.log_prob(agent._a_norm.normalize(actions[cohort]))).mean()
            g=torch.autograd.grad(loss,params);gradients.append(torch.cat([v.flatten() for v in g]).detach())
        a,b=gradients;gradient_report=dict(getup_norm=float(a.norm()),other_norm=float(b.norm()),
            cosine=float(torch.dot(a,b)/(a.norm()*b.norm()).clamp_min(1e-12)),getup_fraction=float(mask.float().mean()))
data=torch.cat(all_records);d=data[:,getup];dh=d[:,:,1]-d[:,:,0];late=d[:,:,2]>=60
result['ppo_probe']=dict(steps=data.shape[0],gradient=gradient_report,
    early_adv=stats(d[:,:,4][~late]),late_adv=stats(d[:,:,4][late]),
    rising_late_adv=stats(d[:,:,4][late & (dh>.002)]),falling_late_adv=stats(d[:,:,4][late & (dh<-.002)]),
    still_late_adv=stats(d[:,:,4][late & (dh.abs()<=.002)]),
    height_adv_correlation=correlation(d[:,:,0][late],d[:,:,4][late]),
    rise_adv_correlation=correlation(dh[late],d[:,:,4][late]),
    late_critic_value=stats(d[:,:,6][late]),late_reward=stats(d[:,:,5][late]),
    late_rising_fraction=float((dh[late]>.002).float().mean()),late_height_change=stats(dh[late]))
result['elapsed_seconds']=time.time()-start;result['complete']=True;save(result)
