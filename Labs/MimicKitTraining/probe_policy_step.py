"""Bounded matched-data policy-step diagnostic; never trains a production policy."""
import sys,copy,json,runpy,math
from pathlib import Path
import torch
root=Path('/workspace/mimickit_trial');sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')]
from learning.ppo_agent import PPOAgent
from learning.distribution_gaussian_diag import DistributionGaussianDiag

def probe(self,batch_size,num_steps):
    batches=[self._exp_buffer.sample(batch_size) for _ in range(num_steps)]
    prepared=[]
    with torch.no_grad():
        for b in batches:
            obs=self._obs_norm.normalize(b['obs']);base=self._model.eval_actor(obs)
            epsilon=(self._a_norm.normalize(b['action'])-base.mean)/base.stddev
            prepared.append((obs.detach(),base.mean.detach(),epsilon.detach(),b['adv'].detach()))
    results=[]
    for sigma,lr in [(0.05,1e-4),(.005,1e-4),(.005,1e-5),(.005,1e-6),(.005,1e-7)]:
        model=copy.deepcopy(self._model)
        model._action_dist._logstd_net.data.fill_(math.log(sigma))
        optimizer=torch.optim.SGD([p for p in model.get_actor_params() if p.requires_grad],lr=lr,momentum=.9)
        first=None
        for i,(obs,mean,epsilon,adv) in enumerate(prepared):
            a=mean+sigma*epsilon
            old=DistributionGaussianDiag(mean,torch.full_like(mean,math.log(sigma)))
            old_logp=old.log_prob(a)
            dist=model.eval_actor(obs);ratio=torch.exp(dist.log_prob(a)-old_logp)
            loss=-torch.minimum(adv*ratio,adv*ratio.clamp(.8,1.2)).mean()
            optimizer.zero_grad();loss.backward()
            grad_norm=float(torch.stack([p.grad.square().sum() for p in model.get_actor_params() if p.grad is not None]).sum().sqrt())
            optimizer.step()
            with torch.no_grad():
                after=model.eval_actor(obs);kl=float(old.kl(after).mean());r=torch.exp(after.log_prob(a)-old_logp)
                metrics=dict(gradient_norm=grad_norm,mean_kl=kl,clip_fraction=float(((r-1).abs()>.2).float().mean()),mean_shift_rms=float((after.mean-mean).square().mean().sqrt()))
            if i==0:first=metrics
        results.append(dict(noise=sigma,actor_lr=lr,first_step=first,after_40_steps=metrics))
    (root/'policy_step_probe.json').write_text(json.dumps(dict(batch_size=batch_size,steps=num_steps,results=results),indent=2))
    print('POLICY_STEP_PROBE_COMPLETE',json.dumps(results),flush=True)
    raise RuntimeError('Bounded policy-step diagnostic complete; no production training')
PPOAgent._update_actor=probe
sys.argv=['train.py','--task','neutral_pose','--worlds','128','--action-noise','0.005','--output-interval','50','--name','policy_step_probe_01','--max-samples','4096','--seconds','180']
runpy.run_path(str(root/'pipeline/train.py'),run_name='__main__')
