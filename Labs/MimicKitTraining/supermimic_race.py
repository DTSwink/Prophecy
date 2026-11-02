"""Experimental SuperMimic-style BPTT vs pinned PPO, evaluated in real MuJoCo.

This is a paper-inspired adaptation, NOT the unreleased official implementation.
The world model uses full physical policy observations (unclipped), executed
actions, and three-frame reward context. Production source/checkpoints are inputs
only. Both workers use identical simulator/task/actor and held-out reset seeds.
"""
import argparse,copy,hashlib,io,json,math,os,random,sys,time,zipfile
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

def write(path,obj):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2,allow_nan=False));tmp.replace(path)

def seed(n):
    random.seed(n);np.random.seed(n);torch.manual_seed(n);torch.cuda.manual_seed_all(n)

def mlp(a,widths,b):
    layers=[]
    for w in widths:layers.extend([nn.Linear(a,w),nn.SiLU()]);a=w
    layers.append(nn.Linear(a,b));return nn.Sequential(*layers)

def lambda_targets(rewards,continuation,timeout_value,values,gamma=.99,lam=.98):
    """Failure has zero bootstrap; timeout bootstraps the pre-reset final state."""
    ret=values[-1];targets=[]
    for t in range(len(rewards)-1,-1,-1):
        ret=rewards[t]+gamma*(timeout_value[t]+continuation[t]*((1-lam)*values[t+1]+lam*ret))
        targets.append(ret)
    return torch.stack(targets[::-1])

class LearnedWorld(nn.Module):
    def __init__(self,mean,std,context):
        super().__init__();self.register_buffer('mean',mean[:146].clone());self.register_buffer('std',std[:146].clone())
        self.dynamics=mlp(146+34,[1024,1024,1024],146)
        nn.init.zeros_(self.dynamics[-1].weight);nn.init.zeros_(self.dynamics[-1].bias)
        self.reward=mlp(146*3+context,[512,512],1)
        self.terminal=mlp(146+context,[256,256],1)
        nn.init.constant_(self.terminal[-1].bias,-5.)

    def step(self,x,a):
        y=x+self.dynamics(torch.cat((x,a),-1))*.1
        # Reproject the body's 6D rotations; all original observations are kept.
        raw=y*self.std+self.mean
        def rotation(v):
            t=F.normalize(v[..., :3],dim=-1,eps=1e-5)
            z=F.normalize(v[..., 3:]-t*(t*v[..., 3:]).sum(-1,keepdim=True),dim=-1,eps=1e-5)
            return torch.cat((t,z),-1)
        raw=torch.cat((raw[:,:1],rotation(raw[:,1:7]),raw[:,7:13],
                       rotation(raw[:,13:97].reshape(-1,14,6)).flatten(1),raw[:,97:]),-1)
        return (raw-self.mean)/self.std

    def heads(self,h,ctx):
        return (self.reward(torch.cat((h.flatten(1),ctx),-1)).squeeze(-1).sigmoid(),
                self.terminal(torch.cat((h[:,-1],ctx),-1)).squeeze(-1))

class Replay:
    def __init__(self,n,device,capacity=256):
        self.n=n;self.capacity=capacity;self.device=device;self.data={};self.count=0;self.ptr=0
    def add(self,**row):
        if not self.data:
            self.data={k:torch.empty((self.capacity,*v.shape),device=self.device,dtype=v.dtype) for k,v in row.items()}
        for k,v in row.items():self.data[k][self.ptr].copy_(v)
        self.ptr=(self.ptr+1)%self.capacity;self.count=min(self.count+1,self.capacity)
    def sample(self,batch,length=8,holdout=False):
        if self.count<length+1:raise ValueError('Insufficient replay')
        # Whole worlds are held out from model fitting. No overlapping-window leakage.
        eligible=torch.arange(self.n,device=self.device)
        eligible=eligible[(eligible%10==0) if holdout else (eligible%10!=0)]
        worlds=eligible[torch.randint(len(eligible),(batch,),device=self.device)]
        start=torch.randint(self.count-length+1,(batch,),device=self.device)
        offset=self.ptr if self.count==self.capacity else 0
        idx=(start[None]+torch.arange(length,device=self.device)[:,None]+offset)%self.capacity
        return {k:v[idx,worlds[None]] for k,v in self.data.items()}

class Context:
    def __init__(self,env,agent):
        self.e=env;self.a=agent;self.device=env._device
        self.nmotion=env._motion_lib.get_num_motions();self.dim=self.nmotion+4
        self.mean=agent._obs_norm._mean.detach();self.std=agent._obs_norm._std.detach()
        self.low=agent._a_norm.normalize(env._action_bound_low)
        self.high=agent._a_norm.normalize(env._action_bound_high)
    def physical(self,obs):return (obs[:,:146]-self.mean[:146])/self.std[:146]
    def commands(self,motion,phase):
        e=self.e;arms=torch.ones((len(motion),2),device=self.device)
        return torch.cat((e._gaits[motion,None],e._directions[motion],e._equipment[motion,None],arms,phase),-1)
    def obs(self,x,motion,phase):
        raw=torch.cat((x*self.std[:146]+self.mean[:146],self.commands(motion,phase)),-1)
        return self.a._obs_norm.normalize(raw)
    def clock_phase(self,motion,times):
        from omni_walk import phase_at
        return phase_at(times,self.e._motion_lib.get_motion_length(motion),self.e._phase_offsets[motion],0.)
    def head_context(self,motion,phase,age,pert):
        return torch.cat((F.one_hot(motion,self.nmotion).float(),phase,age[:,None]/120.,pert[:,None].float()),-1)
    def policy(self,x,motion,phase,sample_actions=False):
        obs=self.obs(x,motion,phase);dist=self.a._model.eval_actor(obs);a=dist.mode
        executed=sample_normalized_action(dist) if sample_actions else a
        return a,executed.clamp(self.low,self.high),self.a._model.eval_phase(obs)

def sample_normalized_action(dist,generator=None):
    """Reparameterized production exploration, before physical action scaling."""
    mean=dist.mode
    noise=torch.randn(mean.shape,device=mean.device,dtype=mean.dtype,generator=generator)
    return mean+dist.stddev*noise

def model_loss(wm,b,ctx):
    x=b['x'][0];h=b['history'][0];alive=torch.ones(len(x),device=x.device)
    loss=0.;state_error=0.;weighted_error=0.;identity=0.;reward_error=0.;terminal_error=0.;weight=0.
    for t in range(b['a'].shape[0]):
        x=wm.step(x,b['a'][t]);h=torch.cat((h[:,1:],x[:,None]),1)
        c=ctx.head_context(b['motion'][t],b['next_phase'][t],b['age'][t]+1,b['pert'][t])
        head_history=h.detach() if getattr(wm,'detach_auxiliary_inputs',False) else h
        reward,logits=wm.heads(head_history,c)
        se=(x-b['next_x'][t]).square().mean(-1)
        vse=((x-b['next_x'][t]).square()*b['value_weights'][t]).mean(-1) if 'value_weights' in b else se
        objective_state=vse if getattr(wm,'value_weighted',False) else se
        if hasattr(wm,'state_loss'):objective_state=wm.state_loss(x,b['next_x'][t])
        if getattr(wm,'value_add_mse',False):objective_state=objective_state+se
        re=(reward-b['base_reward'][t]).square()
        te=F.binary_cross_entropy_with_logits(logits,b['fail'][t].float(),reduction='none')
        state_error+=(se*alive).sum();reward_error+=(re*alive).sum();terminal_error+=(te*alive).sum()
        weighted_error+=(vse*alive).sum()
        identity+=((b['x'][0]-b['next_x'][t]).square().mean(-1)*alive).sum()
        loss+=((objective_state+re+te*.1)*alive).sum();weight+=alive.sum()
        alive=alive*(~b['done'][t]).float()
    loss=loss/weight.clamp_min(1)
    direction_error=x.new_zeros(())
    if getattr(wm,'directional_supervision',False):
        from supermimic_derivatives import directional_loss
        direction_error=directional_loss(wm,b)
        # DDPPO's public implementation uses weight_grad_loss=10. Keep a single
        # predeclared value rather than select it from held-out performance.
        loss=loss+10.*direction_error
    return loss,dict(state_nse=state_error/weight.clamp_min(1),
        identity_nse=identity/weight.clamp_min(1),reward_mse=reward_error/weight.clamp_min(1),term_bce=terminal_error/weight.clamp_min(1),
        value_weighted_state_nse=weighted_error/weight.clamp_min(1),directional_change_mse=direction_error)

def evaluate(env,agent,seed_values,max_ticks=300,exploration=False):
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    import mujoco_warp as mjw
    agent.eval();agent.set_mode(AgentMode.TEST);rows=[]
    with torch.no_grad():
        for s in seed_values:
            seed(s);mjw.reset_data(env._engine._solver.mjw_model,env._engine._solver.mjw_data)
            obs,info=agent._reset_envs();n=env.get_num_envs()
            init=hashlib.sha256(obs.cpu().numpy().tobytes()).hexdigest()
            if not hasattr(env,'_experiment_initial_states'):env._experiment_initial_states={}
            key=(s,exploration,n)
            if key not in env._experiment_initial_states:env._experiment_initial_states[key]=obs.clone()
            initial_error=float((obs-env._experiment_initial_states[key]).abs().max())
            if initial_error>2e-4:raise RuntimeError('Evaluation reset changed materially: '+str(initial_error))
            active=torch.ones(n,device=obs.device,dtype=torch.bool)
            failures=torch.zeros(n,device=obs.device,dtype=torch.bool)
            returns=torch.zeros(n,device=obs.device);length=torch.zeros_like(returns)
            group=env._perturbed_rows.long()*2+(env._gaits[env._motion_ids]==-1).long()
            initial_motion=env._motion_ids.clone()
            # Independent RNG keeps each row's action-noise sequence matched even
            # when policies reset different numbers of other rows.
            noise_rng=torch.Generator(device=obs.device).manual_seed(s+1000000)
            for tick in range(max_ticks):
                action,_=agent._decide_action(obs,info)
                if exploration:
                    dist=agent._model.eval_actor(agent._obs_norm.normalize(obs))
                    action=agent._a_norm.unnormalize(sample_normalized_action(dist,noise_rng))
                obs,reward,done,info=env.step(action)
                returns+=reward*active;length+=active
                failures|=active&(done==DoneFlags.FAIL.value)
                active &= done==DoneFlags.NULL.value
                if not bool(active.any()):break
                obs,info=agent._reset_done_envs(done)
            groups={}
            for i,name in enumerate(['normal_loco','normal_idle','perturbed_loco','perturbed_idle']):
                mask=group==i
                groups[name]=dict(rows=int(mask.sum()),failures=int(failures[mask].sum()),
                    mean_ticks=float(length[mask].mean()),mean_return=float(returns[mask].mean()),unfinished=int(active[mask].sum()))
            rows.append(dict(seed=s,exploration=exploration,initial_observation_sha256=init,initial_max_abs_error=initial_error,groups=groups,
                row_failed=failures.cpu().tolist(),row_group=group.cpu().tolist(),
                row_motion=initial_motion.cpu().tolist(),row_return=returns.cpu().tolist(),row_ticks=length.cpu().tolist()))
    return rows

def imagined_update(wm,buffer,ctx,actor_opt,critic_opt,batch=256,horizon=32,update_critic=True,value_model=None,sample_actions=False):
    a=ctx.a;e=ctx.e;b=buffer.sample(batch,1);x=b['x'][0];history=b['history'][0]
    value_model=a._model if value_model is None else value_model
    motion=b['motion'][0];phase=b['phase'][0];age=b['age'][0];pert=b['pert'][0]
    times=b['times'][0];gamma=.99;lam=.98
    penalty=pert.float()*(e._gaits[motion]!=-1)*float(e._perturb_cfg['loco_failure_penalty'])
    for p in wm.parameters():p.requires_grad_(False)
    critic_params=list(a._model.get_critic_params())
    for p in critic_params:p.requires_grad_(False)
    actor_params=list(a._model.get_actor_params())
    states=[];rewards=[];continues=[];values=[];timeout_values=[];weights=[];phase_loss=0.;bound_loss=0.
    survival=torch.ones(batch,device=x.device);objective=torch.zeros_like(survival)
    start_obs=ctx.obs(x,motion,phase).detach()
    with torch.no_grad():old_mean=a._model.eval_actor(start_obs).mode.clone()
    for t in range(horizon):
        weights.append(survival.detach())
        obs=ctx.obs(x,motion,phase);states.append(obs);values.append(value_model.eval_critic(obs).squeeze(-1))
        raw_action,action,predicted_phase=ctx.policy(x,motion,phase,sample_actions=sample_actions)
        bound_loss+=((raw_action-raw_action.clamp(ctx.low,ctx.high)).square().sum(-1)*survival.detach()).mean()
        next_clock=ctx.clock_phase(motion,times+(t+1)/30.)
        phase_loss+=((predicted_phase-next_clock).square().mean(-1)*(~pert)*survival.detach()).mean()
        phase=torch.where(pert[:,None],F.normalize(predicted_phase,dim=-1,eps=1e-6),next_clock)
        x=wm.step(x,action);history=torch.cat((history[:,1:],x[:,None]),1)
        age=age+1
        base,logit=wm.heads(history,ctx.head_context(motion,phase,age,pert))
        fail=logit.sigmoid();r=base-penalty*fail
        timeout=age>=torch.where(pert,120.,300.)
        vnext=value_model.eval_critic(ctx.obs(x,motion,phase)).squeeze(-1)
        objective+=gamma**t*survival*(r+gamma*(1-fail)*timeout*vnext)
        survival=survival*(1-fail)*(~timeout)
        rewards.append(r);continues.append((1-fail)*(~timeout));timeout_values.append((1-fail)*timeout*vnext)
    final_value=value_model.eval_critic(ctx.obs(x,motion,phase)).squeeze(-1)
    objective+=gamma**horizon*survival*final_value
    actor_loss=-objective.mean()+a._phase_weight*phase_loss/horizon+a._action_bound_weight*bound_loss/horizon
    actor_opt.zero_grad(set_to_none=True);actor_loss.backward()
    norm=nn.utils.clip_grad_norm_(actor_params,1.)
    if not torch.isfinite(norm):raise RuntimeError('Nonfinite imagined actor gradient')
    for p in actor_params:
        if p.grad is not None:p.grad.clamp_(-.1,.1)
    before=[p.detach().clone() for p in actor_params];old_opt=copy.deepcopy(actor_opt.state_dict())
    actor_opt.step()
    with torch.no_grad():
        new_mean=a._model.eval_actor(start_obs).mode
        kl=((new_mean-old_mean)/.075).square().sum(-1).mean()*.5
        rejected=float(kl)>.18
        if rejected:
            for p,v in zip(actor_params,before):p.copy_(v)
            actor_opt.load_state_dict(old_opt)
            for group in actor_opt.param_groups:group['lr']=max(1e-7,group['lr']*.5)
        vs=torch.stack(values+[final_value]).detach();rr=torch.stack(rewards).detach()
        cc=torch.stack(continues).detach();tv=torch.stack(timeout_values).detach()
        target=lambda_targets(rr,cc,tv,vs,gamma,lam).flatten()
        observations=torch.stack(states).detach().flatten(0,1);sample_weight=torch.stack(weights).flatten()
    for p in critic_params:p.requires_grad_(True)
    loss=torch.zeros((),device=x.device)
    for _ in range(5 if update_critic else 0):
        perm=torch.randperm(len(target),device=x.device)
        for idx in perm.chunk(4):
            pred=a._model.eval_critic(observations[idx]).squeeze(-1)
            loss=((pred-target[idx]).square()*sample_weight[idx]).sum()/sample_weight[idx].sum().clamp_min(1e-6)
            critic_opt.zero_grad(set_to_none=True);loss.backward()
            nn.utils.clip_grad_norm_(critic_params,1.);critic_opt.step()
    for p in wm.parameters():p.requires_grad_(True)
    return dict(actor_loss=float(actor_loss.detach()),critic_loss=float(loss.detach()),kl=float(kl),rejected=rejected,
        actor_grad_norm=float(norm),actor_lr=actor_opt.param_groups[0]['lr'])

def run(root,checkpoint,out,method,seconds,training_seed):
    setup_started=time.perf_counter()
    root=Path(root).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    os.environ['PYGLET_HEADLESS']='true';torch.set_num_threads(2)
    sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')];os.chdir(root/'MimicKit')
    import warp as wp,yaml,mujoco_warp as mjw
    from util import mp_util
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from resume import restore
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6793 if method=='ppo' else 6794)
    seed(training_seed)
    cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
    env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
    restored=restore(agent,checkpoint)
    from resume import override_actor_learning_rate,migrate_physical_observation_scales
    restored['actor_learning_rate_override']=override_actor_learning_rate(agent,1.125e-6)
    if cfg.get('perturbed_motion',{}).get('observation_normalization')=='physical_scales_v1':
        restored['observation_normalization_migration']=migrate_physical_observation_scales(agent)
    agent._init_train()
    assert restored['optimizer_restored'] and not agent._need_normalizer_update()
    result=dict(method=method,adaptation='observation-state residual world model; learned reward/failure heads; BPTT32; autoregressive model fit8',
        checkpoint_sha256=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),seed=training_seed,
        gpu=torch.cuda.get_device_name(),torch=torch.__version__,restored=restored,
        seconds_budget=seconds,updates=[],evaluations=[],complete=False)
    provenance=Path(checkpoint).parent/'runtime_provenance.json'
    if provenance.exists():result['verified_inputs']=json.loads(provenance.read_text())
    write(out/'result.json',result)
    result['evaluations'].append(dict(training_seconds=0.,rows=evaluate(env,agent,[481031,481032])))
    seed(training_seed);agent.set_mode(AgentMode.TRAIN);agent.train()
    mjw.reset_data(env._engine._solver.mjw_model,env._engine._solver.mjw_data)
    agent._curr_obs,agent._curr_info=agent._reset_envs()
    ctx=Context(env,agent);buffer=Replay(1024,'cuda:0')
    wm=LearnedWorld(ctx.mean,ctx.std,ctx.dim).cuda()
    opt_wm=torch.optim.Adam(wm.parameters(),lr=2e-4)
    actor_opt=torch.optim.Adam(agent._model.get_actor_params(),lr=2e-4,betas=(.9,.95))
    critic_opt=torch.optim.Adam(agent._model.get_critic_params(),lr=2e-4)
    h=ctx.physical(agent._curr_obs)[:,None].repeat(1,3,1)
    result['common_setup_and_initial_evaluation_seconds']=time.perf_counter()-setup_started
    started=time.perf_counter();updates=0;model_steps=0;sim_steps=0;next_save=300.;snapshots=[];warm_ready=False
    def collect(ticks):
        nonlocal h,sim_steps
        with torch.no_grad():
            for _ in range(ticks):
                obs=agent._curr_obs;x=ctx.physical(obs)
                motion=env._motion_ids.clone();phase=obs[:,-2:].clone()
                age=torch.round(env._time_buf*30).clone();pert=env._perturbed_rows.clone()
                times=(env._time_buf+env._motion_time_offsets).clone()
                action,_=agent._decide_action(obs,agent._curr_info)
                executed=agent._a_norm.normalize(action.clamp(env._action_bound_low,env._action_bound_high))
                next_obs,reward,done,info=env.step(action)
                nx=ctx.physical(next_obs);fail=done==DoneFlags.FAIL.value;ended=done!=DoneFlags.NULL.value
                penalty=pert*(env._gaits[motion]!=-1)*float(env._perturb_cfg['loco_failure_penalty'])
                base=reward+fail*penalty
                assert bool(torch.isfinite(nx).all()) and bool((base>=-1e-5).all()) and bool((base<=1.0001).all())
                buffer.add(x=x,next_x=nx,a=executed,motion=motion,phase=phase,next_phase=next_obs[:,-2:],
                    age=age,pert=pert,times=times,base_reward=base,fail=fail,done=ended,history=h)
                h=torch.cat((h[:,1:],nx[:,None]),1)
                agent._curr_obs,agent._curr_info=agent._reset_done_envs(done)
                reset_x=ctx.physical(agent._curr_obs);h[ended]=reset_x[ended,None].repeat(1,3,1)
                sim_steps+=1024
    while time.perf_counter()-started<seconds:
        if method=='ppo':
            agent._iter=updates;metrics={k:float(v) for k,v in agent._train_iter().items()}
            agent._sample_count=agent._update_sample_count();sim_steps+=1024*32
        else:
            collect(64 if buffer.count==0 else 3)
            for _ in range(10):
                b=buffer.sample(256,8);loss,metrics=model_loss(wm,b,ctx)
                opt_wm.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(wm.parameters(),1.)
                opt_wm.step();model_steps+=1
            metrics={k:float(v.detach()) for k,v in metrics.items()}
            if updates==0:
                # Exercise the complete differentiable path before committing
                # any actor update. Restore both networks and fresh optimizers.
                saved={k:v.detach().clone() for k,v in agent.state_dict().items()}
                ao=copy.deepcopy(actor_opt.state_dict());co=copy.deepcopy(critic_opt.state_dict())
                metrics['gradient_smoke']=imagined_update(wm,buffer,ctx,actor_opt,critic_opt,batch=32,horizon=32)
                agent.load_state_dict(saved);actor_opt.load_state_dict(ao);critic_opt.load_state_dict(co)
                del saved,ao,co
            if model_steps%100==0:
                with torch.no_grad():_,held=model_loss(wm,buffer.sample(512,8,holdout=True),ctx)
                held={k:float(v) for k,v in held.items()};metrics['heldout']=held
                warm_ready=model_steps>=500 and held['state_nse']<.05 and held['state_nse']<held['identity_nse']*.8 and held['reward_mse']<.02
            if warm_ready:metrics.update(imagined_update(wm,buffer,ctx,actor_opt,critic_opt))
            metrics['actor_enabled']=warm_ready;metrics['model_steps']=model_steps
        torch.cuda.synchronize();updates+=1;elapsed=time.perf_counter()-started
        result['updates'].append(dict(update=updates,seconds=elapsed,transitions=sim_steps,metrics=metrics))
        if elapsed>=next_save:
            filename=out/('policy_'+str(round(elapsed))+'.pt');torch.save({k:v.detach().cpu() for k,v in agent.state_dict().items()},filename)
            snapshots.append((elapsed,filename));next_save+=300.
        if updates%10==0:
            write(out/'result.json',result);print('PROGRESS',method,round(elapsed),updates,metrics,flush=True)
    result['training_seconds']=time.perf_counter()-started
    torch.save({k:v.detach().cpu() for k,v in agent.state_dict().items()},out/'policy_final.pt')
    snapshots.append((result['training_seconds'],out/'policy_final.pt'))
    if method!='ppo':torch.save(dict(model=wm.state_dict(),optimizer=opt_wm.state_dict()),out/'world_model.pt')
    result['actor_ever_updated']=method=='ppo' or any('actor_loss' in x['metrics'] for x in result['updates'])
    # Training is over; evaluation cannot change training RNG/history or its budget.
    for elapsed,filename in snapshots:
        agent.load_state_dict(torch.load(filename,map_location='cuda:0',weights_only=True))
        result['evaluations'].append(dict(training_seconds=elapsed,policy=filename.name,
            rows=evaluate(env,agent,[481031,481032,481033,481034])))
        write(out/'result.json',result)
    result['complete']=True;write(out/'result.json',result);print('COMPLETE',method,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--checkpoint',required=True)
    p.add_argument('--output',required=True);p.add_argument('--method',choices=['ppo','world_model'],required=True)
    p.add_argument('--seconds',type=float,default=1800);p.add_argument('--seed',type=int,default=57361)
    a=p.parse_args();run(a.root,a.checkpoint,a.output,a.method,a.seconds,a.seed)
