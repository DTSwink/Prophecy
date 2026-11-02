"""Isolated RWM history/ensemble correction; frozen-policy prediction screen.

Uses the released rsl_rl_rwm RNNBase and MLPStateHead, commit recorded by the
launcher. Our ball-joint increment/FK adapter and residual warm start differ
from the paper. This diagnostic makes no policy-learning speed claim.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import torch
from torch import nn
import supermimic_race as base
from supermimic_increments import IncrementWorld, apply_increments


def official_module(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def prefix_indices(done, starts, worlds, history=31):
    """Left-pad history, excluding every transition before the last reset.

    done[t] means the action at t ended its episode; it must not enter the
    context for x[t+1]. Current action is supplied separately by step().
    """
    offsets=torch.arange(-history,0,device=done.device)[:,None]
    ids=starts[None]+offsets
    available=ids>=0;safe=ids.clamp_min(0)
    ends=done[safe,worlds[None]]&available
    valid=available&(ends.flip(0).long().cumsum(0).flip(0)==0)
    return safe,valid


class RecurrentCorrection(nn.Module):
    def __init__(self, warm, source):
        super().__init__();self.warm=warm
        for p in warm.parameters():p.requires_grad_(False)
        rnn=official_module(Path(source)/'rnn.py','official_rwm_rnn')
        mlp=official_module(Path(source)/'mlp.py','official_rwm_mlp')
        cfg=dict(rnn_type='gru',rnn_num_layers=2,rnn_hidden_size=256,
                 state_mean_shape=[128],state_logstd_shape=None)
        self.core=rnn.RNNBase(180,str(warm.mean.device),cfg)
        self.heads=nn.ModuleList([mlp.MLPStateHead(256,86,str(warm.mean.device),cfg) for _ in range(5)])
        for head in self.heads:
            nn.init.zeros_(head.state_mean_layers[-1].weight)
            nn.init.zeros_(head.state_mean_layers[-1].bias)
        self.head_ids=None;self.uncertainty=None

    @property
    def terminal(self):return self.warm.terminal

    def features(self,x,a):
        raw=x*self.warm.std+self.warm.mean
        return (self.warm.features(raw,a)-self.warm.input_mean)/self.warm.input_std

    def begin(self, features, head_ids=None):
        # One shared GRU pass for the concatenated, independently bootstrapped
        # members. No hidden state can leak from one member/batch into another.
        self.core.reset();self.head_ids=head_ids
        if features.shape[1]:self.core(features[:,:,:146],features[:,:,146:])

    def begin_from_rows(self,rows,branch):
        n=len(rows[branch]['x']);dev=rows[branch]['x'].device
        ends=torch.stack([r['ended'] for r in rows])
        idx,valid=prefix_indices(ends,torch.full((n,),branch,device=dev),torch.arange(n,device=dev))
        xs=torch.stack([r['x'] for r in rows]);acts=torch.stack([r['action'] for r in rows])
        worlds=torch.arange(n,device=dev)[None]
        f=self.features(xs[idx,worlds].flatten(0,1),acts[idx,worlds].flatten(0,1))
        self.begin((f.reshape(31,n,-1)*valid[:,:,None]).transpose(0,1))

    def step(self,x,a):
        raw=x*self.warm.std+self.warm.mean;f=self.features(x,a)
        y=self.core(f[:,:146,None].transpose(1,2),f[:,146:,None].transpose(1,2))
        zero=y.new_zeros((len(y),1,86))
        means=torch.stack([head(y,zero)[0] for head in self.heads])
        self.uncertainty=means.std(0).square().mean(-1).sqrt()
        correction=means.mean(0) if self.head_ids is None else means[self.head_ids,torch.arange(len(y),device=y.device)]
        delta=(self.warm.dynamics(f)+correction)*self.warm.delta_std+self.warm.delta_mean
        return (self.warm.skeleton(apply_increments(raw,delta))-self.warm.mean)/self.warm.std

    def state_loss(self,pred,target):return self.warm.state_loss(pred,target)


def failure_windows(done,failure,length=8):
    """Training windows whose first episode boundary is a failure, never timeout.

    A failure after a reset cannot qualify a window because the fitted loss is
    masked at its first boundary. Entire validation worlds remain excluded.
    """
    count=done.shape[0]-length+1
    alive=torch.ones((count,done.shape[1]),device=done.device,dtype=torch.bool)
    selected=torch.zeros_like(alive)
    for tick in range(length):
        selected|=alive&failure[tick:tick+count]
        alive&=~done[tick:tick+count]
    selected&=(torch.arange(done.shape[1],device=done.device)%10!=0)[None]
    return selected.nonzero()


class Windows:
    def __init__(self,data,warm):
        self.d=data;self.warm=warm;self.t,self.n=data['done'].shape
        self.failure_pool=failure_windows(data['done'],data['boundary_failure']) if 'boundary_failure' in data else None
        self.priority_samples=0
        with torch.no_grad():
            self.features=warm.features(data['x'].flatten(0,1)*warm.std+warm.mean,data['a'].flatten(0,1))
            self.features=((self.features-warm.input_mean)/warm.input_std).reshape(self.t,self.n,180)

    def sample(self,batch,length,holdout=False,priority_fraction=0.):
        assert 0<=priority_fraction<=1
        assert not (holdout and priority_fraction), 'Heldout distribution must remain uniform'
        dev=self.d['x'].device;eligible=torch.arange(self.n,device=dev)
        eligible=eligible[(eligible%10==0) if holdout else (eligible%10!=0)]
        worlds=eligible[torch.randint(len(eligible),(batch,),device=dev)]
        starts=torch.randint(self.t-length+1,(batch,),device=dev)
        count=round(batch*priority_fraction)
        if count:
            assert length==8 and self.failure_pool is not None and len(self.failure_pool)>0
            chosen=self.failure_pool[torch.randint(len(self.failure_pool),(count,),device=dev)]
            starts[:count]=chosen[:,0];worlds[:count]=chosen[:,1]
            self.priority_samples+=count
        ids=starts[None]+torch.arange(length,device=dev)[:,None]
        b={k:v[ids,worlds[None]] for k,v in self.d.items()}
        pi,mask=prefix_indices(self.d['done'],starts,worlds)
        b['prefix']=(self.features[pi,worlds[None]]*mask[:,:,None]).transpose(0,1)
        return b


def com2_error(predicted,target,reference_speed,enabled):
    # Idle has a zero reference speed; exclude it without ever creating NaNs.
    scaled=(predicted-target)/reference_speed.clamp_min(.1)[:,None]
    return scaled.square().sum(-1)*enabled


def loss_parts(model,b,scorer=None):
    if isinstance(model,RecurrentCorrection):
        n=len(b['x'][0]);assert n%5==0
        model.begin(b['prefix'],torch.arange(n,device=b['x'].device)//(n//5))
    x=b['x'][0];alive=torch.ones(len(x),device=x.device);total=x.new_zeros(());weight=total.clone()
    auxiliary=total.clone();aux_weight=total.clone()
    for t in range(len(b['a'])):
        x=model.step(x,b['a'][t]);error=model.state_loss(x,b['next_x'][t])
        total+=(error*alive).sum();weight+=alive.sum()
        if scorer is not None:
            motion=b['motion'][t];enabled=b['pert'][t]&(scorer.e._gaits[motion]!=-1)
            speed=scorer.e._com2_targets[motion].norm(dim=-1)
            velocity=scorer.com2(x,x.new_zeros((len(x),2)))
            auxiliary+=(com2_error(velocity,b['com2'][t],speed,enabled)*alive).sum()
            aux_weight+=(alive*enabled).sum()
        alive=alive*~b['done'][t]
    return total/weight.clamp_min(1),auxiliary/aux_weight.clamp_min(1)


def loss(model,b):return loss_parts(model,b)[0]


@torch.no_grad()
def check(model,b,scorer=None):
    if isinstance(model,RecurrentCorrection):model.begin(b['prefix'])
    x=b['x'][0];alive=torch.ones(len(x),device=x.device,dtype=torch.bool);out={}
    for t in range(len(b['a'])):
        x=model.step(x,b['a'][t])
        if t+1 in (1,8,32):
            error=(x-b['next_x'][t]).square().mean(-1)
            r=dict(rows=int(alive.sum()),state_nse=float(error[alive].mean()))
            if scorer is not None:
                motion=b['motion'][t];enabled=alive&b['pert'][t]&(scorer.e._gaits[motion]!=-1)
                predicted=scorer.com2(x,x.new_zeros((len(x),2)));diff=predicted-b['com2'][t]
                r['com2_rows']=int(enabled.sum())
                r['com2_rmse_mps']=float(diff.square().sum(-1)[enabled].mean().sqrt())
                speed=scorer.e._com2_targets[motion].norm(dim=-1)
                r['com2_relative_mse']=float(com2_error(predicted,b['com2'][t],speed,enabled)[enabled].mean())
            if isinstance(model,RecurrentCorrection):
                u=model.uncertainty[alive];e=error[alive]
                r['uncertainty_mean']=float(u.mean())
                if float(u.std())>1e-9 and len(u)>2:
                    r['uncertainty_error_correlation']=float(torch.corrcoef(torch.stack((u,e)))[0,1])
            out['h'+str(t+1)]=r
        alive&=~b['done'][t]
    return out


def gradient_coefficient(state_gradient,auxiliary_gradient,ratio):
    """Calibrate once on training data; never select weights on held-out results."""
    assert 0 < ratio <= 1
    return float(ratio*state_gradient.norm()/auxiliary_gradient.norm().clamp_min(1e-12))


def run(root,checkpoint,output,method,source,seconds=180,task_calibration=False,
        task_gradient_ratio=0.,calibration_seeds='984102',failure_calibration=False):
    started=time.perf_counter();root=Path(root).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')];os.chdir(root/'MimicKit')
    os.environ['PYGLET_HEADLESS']='true';torch.set_num_threads(2)
    import warp as wp,yaml,mujoco_warp as mjw
    from util import mp_util
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from resume import restore,migrate_physical_observation_scales
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    from supermimic_exact_reward import ExactReward
    from supermimic_rollout_calibration import capture,predict,BRANCHES
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6893);base.seed(57361)
    cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
    env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0');restore(agent,checkpoint)
    if cfg['perturbed_motion'].get('observation_normalization')=='physical_scales_v1':migrate_physical_observation_scales(agent)
    agent._init_train();agent.eval();initial={k:v.detach().clone() for k,v in agent.state_dict().items()}
    for p in agent.parameters():p.requires_grad_(False)
    ctx=base.Context(env,agent);scorer=ExactReward(ctx)
    warm=IncrementWorld(ctx.mean,ctx.std,ctx.dim,env._kin_char_model,env._key_body_ids).cuda()
    file=next(Path('/kaggle/input').rglob('increments-audited-world.pt'))
    digest=hashlib.sha256(file.read_bytes()).hexdigest()
    assert digest=='7369ac6f091fc87e8d0e62efddd30a86687d266f676273e1885596772205f430'
    warm.load_state_dict(torch.load(file,map_location='cuda:0',weights_only=True)['model'])
    report=dict(kind='rwm_history_prediction_screen',method=method,complete=False,actor_updates=0,
        checkpoint_sha256=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),warm_sha256=digest,
        fit_budget_seconds=seconds,prior_fit_seconds=326.300588,checks=[],calibration=[],
        limitations='Frozen policy. Model-prediction test, not policy-learning gain. Isolated adaptation, not an exact paper reproduction.',
        task_gradient_ratio=task_gradient_ratio,calibration_seeds=[int(s) for s in calibration_seeds.split(',')])
    print('RWM_STARTED',json.dumps(report),flush=True)
    shared=output.parent/'rwm-shared-data.pt';collect_start=time.perf_counter()
    if method=='control':
        agent.set_mode(AgentMode.TRAIN);base.seed(849103)
        mjw.reset_data(env._engine._solver.mjw_model,env._engine._solver.mjw_data)
        obs,info=agent._reset_envs();data={k:[] for k in ('x','next_x','a','done','motion','pert','com2','boundary_failure')}
        for tick in range(256):
            x=ctx.physical(obs).clone();motion=env._motion_ids.clone();pert=env._perturbed_rows.clone()
            action,_=agent._decide_action(obs,info)
            executed=agent._a_norm.normalize(action.clamp(env._action_bound_low,env._action_bound_high))
            nxt,_,done,info=env.step(action)
            com2=(env._engine.get_body_vel(env._get_char_id())[:,env._com2_ids,:2]*env._com2_masses[:,None]).sum(1)
            for k,v in dict(x=x,next_x=ctx.physical(nxt),a=executed,done=done!=DoneFlags.NULL.value,
                           motion=motion,pert=pert,com2=com2,
                           boundary_failure=(done==DoneFlags.FAIL.value)&pert&(env._gaits[motion]!=-1)).items():data[k].append(v.clone())
            obs,info=agent._reset_done_envs(done)
        data={k:torch.stack(v) for k,v in data.items()}
        temp=shared.with_suffix('.partial');torch.save({k:v.cpu() for k,v in data.items()},temp);temp.replace(shared)
    else:
        deadline=time.perf_counter()+180
        while not shared.exists():
            if time.perf_counter()>deadline:raise TimeoutError('Shared data missing')
            time.sleep(.25)
        data=torch.load(shared,map_location='cuda:0',weights_only=True)
    report['collection_or_wait_seconds']=time.perf_counter()-collect_start
    report['dataset_sha256']={k:hashlib.sha256(v.cpu().numpy().tobytes()).hexdigest() for k,v in data.items()}
    windows=Windows(data,warm);base.seed(849104);validation=windows.sample(512,32,True)
    base.seed(849105)
    model=RecurrentCorrection(warm,source).cuda() if method=='recurrent' else warm
    assert method in ('control','recurrent','com2','failure_replay')
    if method!='recurrent':
        for p in warm.parameters():p.requires_grad_(False)
        for p in warm.dynamics.parameters():p.requires_grad_(True)
    params=[p for p in model.parameters() if p.requires_grad]
    original=[p.detach().clone() for p in params]
    optimizer=torch.optim.Adam(params,lr=1e-4 if method=='recurrent' else 2e-4,weight_decay=1e-5 if method=='recurrent' else 0)
    report['trainable_parameters']=sum(p.numel() for p in params)
    task_scorer=scorer if task_calibration or failure_calibration else None;task_weight=0.
    if failure_calibration:
        assert method in ('control','failure_replay') and not task_calibration
        report['kind']='failure_replay_prediction_screen'
        train_worlds=sum(w%10!=0 for w in range(windows.n))
        report['failure_replay']=dict(qualifying_training_windows=len(windows.failure_pool),
            uniform_qualifying_fraction=len(windows.failure_pool)/((windows.t-7)*train_worlds),
            candidate_fraction=.5 if method=='failure_replay' else 0.,
            task_scope='Perturbed locomotion FAIL only; no timeout/success/after-reset/heldout leakage')
    if task_calibration:
        assert method in ('control','com2')
        report['kind']='com2_prediction_screen'
        with torch.no_grad():
            xs=data['next_x'].flatten(0,1);actual=data['com2'].flatten(0,1);errors=[]
            for start in range(0,len(xs),4096):
                v=xs[start:start+4096];errors.append((scorer.com2(v,v.new_zeros((len(v),2)))-actual[start:start+4096]).abs().max())
            error=float(torch.stack(errors).max());assert error<.002,error
            report['simulator_com2_max_abs_error_mps']=error
        base.seed(849107);calibration=windows.sample(320,8)
        state_term,task_term=loss_parts(model,calibration,scorer)
        weight=.5*float(state_term.detach())/max(1e-9,float(task_term.detach()))
        def grad(value):
            return torch.cat([g.flatten() for g in torch.autograd.grad(value,params,retain_graph=True)])
        gs=grad(state_term);gt_raw=grad(task_term)
        if task_gradient_ratio:weight=gradient_coefficient(gs,gt_raw,task_gradient_ratio)
        gt=gt_raw*weight
        report['task_loss_calibration']=dict(state_loss=float(state_term.detach()),auxiliary_loss=float(task_term.detach()),
            coefficient=weight,initial_aux_to_state_loss_ratio=weight*float(task_term.detach())/float(state_term.detach()),auxiliary_to_state_gradient_norm=float(gt.norm()/gs.norm().clamp_min(1e-12)),
            gradient_cosine=float(torch.nn.functional.cosine_similarity(gs[None],gt[None])),training_worlds_only=True)
        task_weight=weight if method=='com2' else 0.
        report['task_weight']=task_weight
        del gs,gt,gt_raw,state_term,task_term,calibration
    report['setup_and_collection_seconds']=time.perf_counter()-started
    report['checks'].append(dict(fit_seconds=0,steps=0,metrics=check(model,validation,task_scorer)))
    # Matching warm starts must produce the same physical prediction before fit.
    if isinstance(model,RecurrentCorrection):
        model.begin(validation['prefix']);parity=float((model.step(validation['x'][0],validation['a'][0])-warm.step(validation['x'][0],validation['a'][0])).abs().max())
        assert parity==0,parity
        report['initial_prediction_max_abs_delta']=parity
    print('RWM_DATA_READY',json.dumps({k:v for k,v in report.items() if k!='calibration'}),flush=True)
    base.seed(849106);fit_start=time.perf_counter();steps=0;next_check=60.;checks_seconds=0.;regressions=0
    while time.perf_counter()-fit_start<seconds:
        b=windows.sample(320,8,priority_fraction=.5 if method=='failure_replay' else 0.);optimizer.zero_grad(set_to_none=True)
        state_term,task_term=loss_parts(model,b,task_scorer if task_weight else None)
        value=state_term+task_weight*task_term;value.backward()
        norm=nn.utils.clip_grad_norm_(params,1.);assert torch.isfinite(norm),norm
        optimizer.step();torch.cuda.synchronize();steps+=1;elapsed=time.perf_counter()-fit_start
        if steps==1:print('RWM_FIT_VERIFIED',method,float(value),float(norm),flush=True)
        if elapsed>=next_check:
            cs=time.perf_counter();metrics=check(model,validation,task_scorer);checks_seconds+=time.perf_counter()-cs
            report['checks'].append(dict(fit_seconds=elapsed,steps=steps,metrics=metrics))
            base.write(output/'result.json',report);print('RWM_CHECK',method,json.dumps(report['checks'][-1]),flush=True);next_check+=60.
            worse=metrics['h8']['state_nse']>report['checks'][0]['metrics']['h8']['state_nse']*1.5
            regressions=regressions+1 if worse else 0
            if regressions>=2:report['early_stop']='Heldout8tick state error >150% of initial at two checks';break
    report.update(fit_seconds=time.perf_counter()-fit_start,checks_seconds=checks_seconds,optimizer_steps=steps,
        model_parameter_delta_l2=float(sum((p-q).square().sum() for p,q in zip(params,original)).sqrt()),
        priority_selected_windows=windows.priority_samples)
    assert report['model_parameter_delta_l2']>0
    report['checks'].append(dict(fit_seconds=report['fit_seconds'],steps=steps,metrics=check(model,validation,task_scorer)))
    model.eval()
    for eval_seed,noisy in [(s,n) for s in report['calibration_seeds'] for n in [False,True]]:
        rows,groups,audit=capture(ctx,scorer,eval_seed,noisy);predictions=[]
        for branch in BRANCHES:
            for closed in [False,True]:predictions.extend(predict(ctx,model,scorer,rows,groups,branch,closed,eval_seed))
        report['calibration'].append(dict(seed=eval_seed,noisy=noisy,audit=audit,predictions=predictions))
        base.write(output/'result.json',report)
        print('RWM_CALIBRATION',method,json.dumps(dict(noisy=noisy,branch0=[dict(horizon=r['horizon'],**r['groups']['perturbed_loco']) for r in predictions if r['branch']==0 and r['closed_loop']])),flush=True)
    delta=max(float((v-initial[k]).abs().max()) for k,v in agent.state_dict().items());assert delta==0
    report.update(complete=True,policy_max_abs_delta=delta,total_seconds=time.perf_counter()-started)
    torch.save(dict(model=model.state_dict(),method=method),output/'world_model.pt')
    report['model_sha256']=hashlib.sha256((output/'world_model.pt').read_bytes()).hexdigest()
    base.write(output/'result.json',report);print('RWM_COMPLETE',method,report['total_seconds'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for k in ['root','checkpoint','output','method','source']:parser.add_argument('--'+k,required=True)
    parser.add_argument('--seconds',type=int,default=180)
    parser.add_argument('--task-calibration',action='store_true')
    parser.add_argument('--task-gradient-ratio',type=float,default=0.)
    parser.add_argument('--calibration-seeds',default='984102')
    parser.add_argument('--failure-calibration',action='store_true')
    run(**vars(parser.parse_args()))
