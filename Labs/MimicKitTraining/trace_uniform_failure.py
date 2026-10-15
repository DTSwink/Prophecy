"""Bounded read-only reproduction: first bad physics state and first PPO gradient.

No production settings change. Keeps one failure snapshot, not per-update models.
"""
import os, sys, json, runpy, time
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial')
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import torch
import numpy as np
from agent_noise import PerAgentNoisePPO
from learning.distribution_gaussian_diag import DistributionGaussianDiag

OUT=ROOT/'uniform_failure_trace'
OUT.mkdir(exist_ok=False)
original_init=PerAgentNoisePPO.__init__
original_loss=PerAgentNoisePPO._compute_actor_loss
original_update=PerAgentNoisePPO._update_actor

def emit(name,data):
    (OUT/(name+'.json')).write_text(json.dumps(data,indent=2))
    print('TRACE '+name+' '+json.dumps(data),flush=True)

def init(self,*args,**kwargs):
    original_init(self,*args,**kwargs)
    env=self._env;eng=env._engine;char=env._get_char_id();step=env.step
    previous=[]
    def state():
        return {key:getattr(eng,'get_'+key)(char).detach().clone() for key in
                ['body_pos','body_rot','body_vel','body_ang_vel','dof_pos','dof_vel']}
    def traced_step(action):
        before=state();before['action']=action.detach().clone()
        before['episode_step']=env._timestep_buf.clone()
        result=step(action)
        after=state();after['obs']=result[0].detach().clone();after['reward']=result[1].detach().clone()
        bad=~torch.isfinite(after['obs']).all(-1)
        if bool(bad.any()):
            ids=bad.nonzero().flatten();records={}
            for label,snapshot in [('before',before),('after',after)]+[(f'previous{i}',s) for i,s in enumerate(previous)]:
                for key,value in snapshot.items():records[label+'_'+key]=value[ids].cpu().numpy()
            np.savez_compressed(OUT/'first_invalid.npz',worlds=ids.cpu().numpy(),**records)
            torch.save(self.state_dict(),OUT/'policy_at_failure.pt')
            summary={key:dict(finite=bool(torch.isfinite(value[ids]).all()),
                             finite_abs_max=float(torch.nan_to_num(value[ids],nan=0.,posinf=0.,neginf=0.).abs().max()))
                     for key,value in after.items()}
            emit('first_invalid',dict(iteration=self._iter,mode=str(self._mode),worlds=ids.cpu().tolist(),
                 episode_steps=before['episode_step'][ids].cpu().tolist(),
                 action_finite=bool(torch.isfinite(action).all()),action_abs_max=float(action.abs().max()),
                 sigma=self.agent_action_logstd.exp()[ids].cpu().flatten().tolist(),after=summary))
            raise FloatingPointError('First invalid state captured before subsequent action or learning')
        previous.append(before)
        if len(previous)>3:previous.pop(0)
        return result
    env.step=traced_step

def loss(self,batch):
    result=original_loss(self,batch)
    if not hasattr(self,'_first_gradient_recorded'):
        self._first_gradient_recorded=True
        mask=batch['rand_action_mask']==1
        obs=self._obs_norm.normalize(batch['obs'])[mask]
        means=self._model.eval_actor(obs).mean
        sigma=batch['action_logstd'][mask].exp().expand_as(means)
        action=self._a_norm.normalize(batch['action'])[mask]
        eps=((action-means)/sigma).detach()
        parameters=[p for p in self._model.get_actor_params() if p.requires_grad]
        values={}
        for label,sd in [('uniform',sigma),('original_fixed',torch.full_like(sigma,.05))]:
            sample=means.detach()+sd*eps
            old=DistributionGaussianDiag(means.detach(),sd.log())
            current=DistributionGaussianDiag(means,sd.log())
            ratio=(current.log_prob(sample)-old.log_prob(sample)).exp()
            objective=-(batch['adv'][mask]*ratio).mean()
            gradients=torch.autograd.grad(objective,parameters,retain_graph=True)
            values[label]=dict(gradient_norm=float(sum(g.square().sum() for g in gradients).sqrt()))
        actual=DistributionGaussianDiag(means,batch['action_logstd'][mask].expand_as(means))
        log_ratio=actual.log_prob(action)-batch['a_logp'][mask]
        values['before_any_actor_step']=dict(max_abs_log_ratio=float(log_ratio.abs().max()),
            sigma_min=float(sigma.min()),sigma_max=float(sigma.max()),samples=int(mask.sum()),
            actual_gradient_norm=float(sum(g.square().sum() for g in torch.autograd.grad(
                result['actor_loss'],parameters,retain_graph=True)).sqrt()))
        emit('first_gradient',values)
    return result

def update(self,*args,**kwargs):
    with torch.no_grad():
        obs=self._obs_norm.normalize(self._exp_buffer.get_data_flat('obs')[:512])
        before=self._model.eval_actor(obs).mean.clone()
    result=original_update(self,*args,**kwargs)
    with torch.no_grad():
        after=self._model.eval_actor(obs).mean
        record=dict(iteration=self._iter,mean_shift_rms=float((after-before).square().mean().sqrt()),
                    mean_abs_max=float(after.abs().max()),clip_fraction=float(result['clip_frac']))
    with (OUT/'updates.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
    return result

PerAgentNoisePPO.__init__=init
PerAgentNoisePPO._compute_actor_loss=loss
PerAgentNoisePPO._update_actor=update
sys.argv=['train.py','--task','neutral_pose','--worlds','512','--action-noise','0.05',
          '--per-agent-noise','--evaluate','--output-interval','50','--max-samples','1572864',
          '--seconds','240','--name','uniform512_trace_01']
runpy.run_path(str(ROOT/'pipeline/train.py'),run_name='__main__')
