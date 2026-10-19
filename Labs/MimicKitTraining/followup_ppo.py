"""Isolated fixed-shape PPO candidate. No launcher or automatic installation."""
import copy
import torch
from util import mp_util


def actor_loss(agent,batch):
    obs=agent._obs_norm.normalize(batch['obs'])
    hidden=agent._model._actor_layers(obs)
    dist=agent._model._action_dist(hidden)
    logp=dist.log_prob(agent._a_norm.normalize(batch['action']))
    ratio=torch.exp(logp-batch['a_logp'])
    mask=(batch['rand_action_mask']==1.).to(ratio.dtype)
    def mean(value):return (value*mask).sum()/mask.sum()
    loss=-mean(torch.minimum(batch['adv']*ratio,batch['adv']*ratio.clamp(1-agent._ppo_clip_ratio,1+agent._ppo_clip_ratio)))
    info=dict(actor_loss=loss,clip_frac=mean((abs(ratio-1)>agent._ppo_clip_ratio).float()).detach(),imp_ratio=mean(ratio).detach())
    if agent._action_bound_weight:
        bound=mean(agent._compute_action_bound_loss(dist));info['action_bound_loss']=bound.detach();loss=loss+agent._action_bound_weight*bound
    if agent._action_entropy_weight:
        entropy=mean(dist.entropy());info['action_entropy']=entropy.detach();loss=loss-agent._action_entropy_weight*entropy
    if agent._action_reg_weight:
        reg=mean(dist.param_reg());info['action_reg_loss']=reg.detach();loss=loss+agent._action_reg_weight*reg
    phase=agent._model._phase_out(hidden)
    if agent._model._unit_phase:phase=torch.nn.functional.normalize(phase,dim=-1,eps=1e-6)
    mse=(phase-batch['next_phase']).square().mean();weighted=agent._phase_weight*mse
    info.update(actor_loss=loss+weighted,phase_prediction_mse=mse.detach(),phase_prediction_weighted=weighted.detach(),auto_phase_mse=mse.detach(),auto_phase_weighted=weighted.detach())
    return info


class CapturedStep:
    def __init__(self,agent,kind,batch):
        assert not mp_util.enable_mp() and not agent._use_mixed_precision
        self.wrapper=getattr(agent,'_'+kind+'_optimizer');opt=self.wrapper._optimizer
        assert isinstance(opt,torch.optim.SGD)
        # Capturing must not consume training, RNG or optimizer state.
        params=self.wrapper._param_list;saved=[p.detach().clone() for p in params]
        state=copy.deepcopy(opt.state_dict());steps=self.wrapper._steps
        rng=torch.cuda.get_rng_state()
        self.batch={k:v.clone() for k,v in batch.items()}
        loss_fn=(lambda b:actor_loss(agent,b)) if kind=='actor' else agent._compute_critic_loss
        def step():
            opt.zero_grad(set_to_none=True)
            self.info=loss_fn(self.batch)
            gradients=torch.autograd.grad(self.info[kind+'_loss'],params)
            for p,gradient in zip(params,gradients):p.grad=gradient
            if self.wrapper._enable_grad_clip():self.wrapper._clip_grads(self.wrapper._grad_clip)
            opt.step()
            self.info={key:value.detach() for key,value in self.info.items()}
        stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(stream):
            for _ in range(3):step()
        torch.cuda.current_stream().wait_stream(stream)
        self.graph=torch.cuda.CUDAGraph()
        with torch.cuda.graph(self.graph,stream=stream):step()
        # Restore IN PLACE: captured graph points to allocated momentum tensors.
        with torch.no_grad():
            for p,value in zip(params,saved):p.copy_(value)
            for group,old_group in zip(opt.param_groups,state['param_groups']):
                for p,ident in zip(group['params'],old_group['params']):
                    prior=state['state'].get(ident,{})
                    for key,value in opt.state[p].items():
                        if torch.is_tensor(value):
                            if key in prior:value.copy_(prior[key])
                            else:value.zero_()
        self.wrapper._steps=steps;torch.cuda.set_rng_state(rng)

    def __call__(self,batch):
        for key,value in batch.items():self.batch[key].copy_(value)
        self.graph.replay();self.wrapper._steps+=1
        return self.info


def install(agent,capture=True):
    """Install only on a disposable test learner; call after restore."""
    import types
    originals={k:getattr(agent,'_update_'+k) for k in ('actor','critic')}
    graphs={}
    def update(kind,batch_size,steps):
        info={}
        for _ in range(steps):
            batch=agent._exp_buffer.sample(batch_size)
            if capture:
                if kind not in graphs:graphs[kind]=CapturedStep(agent,kind,batch)
                result=graphs[kind](batch)
            else:
                result=actor_loss(agent,batch) if kind=='actor' else agent._compute_critic_loss(batch)
                getattr(agent,'_'+kind+'_optimizer').step(result[kind+'_loss'])
            for key,value in result.items():info[key]=info[key]+value if key in info else value.clone()
        return {key:value/steps for key,value in info.items()}
    for kind in originals:
        setattr(agent,'_update_'+kind,lambda size,steps,k=kind:update(k,size,steps))
    def uninstall():
        torch.cuda.synchronize()
        for kind,method in originals.items():setattr(agent,'_update_'+kind,method)
        graphs.clear()
    return uninstall
