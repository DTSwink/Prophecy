"""Independent Gaussian likelihood/gradient/KL and allocation checks."""
import sys, os, json, math, zipfile
from pathlib import Path
import torch

remote=os.name!='nt'
if remote:
    root=Path('/workspace/mimickit_trial/normal-idle-preflight')
    root.mkdir(exist_ok=True)
    with zipfile.ZipFile('/workspace/mimickit_trial/idle-leg-source.zip') as z:z.extractall(root)
else:
    root=Path('Saved/MimicKitLocomotion/normal-idle-noise-20261030/unit_source')
sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')]
from cohort_noise import apply_noise_offset,normal_idle_mask
from idle_minus_allocation import idle_layout
from learning.distribution_gaussian_diag import DistributionGaussianDiag

device='cuda' if remote else 'cpu'
torch.manual_seed(7)
cfg={'idle_row_fraction':.07,'perturbed_motion':{'fraction':.7,'idle_minus_min_fraction':.03}}
assert idle_layout(cfg,2048)==(183,83,62)
cfg['perturbed_motion']['normal_idle_min_fraction']=.02
assert idle_layout(cfg,2048)==(203,103,62)
from types import SimpleNamespace
env=SimpleNamespace(_gaits=torch.tensor([-1,-1,-1,-1,0,-1]),_fixed_motion_ids=torch.arange(6),
    _perturbed_rows=torch.tensor([0,0,1,1,0,0],dtype=torch.bool),
    _recovery_rows=torch.tensor([0,0,0,0,0,1],dtype=torch.bool),
    _final=SimpleNamespace(minus=torch.tensor([0,1,0,0,0,0],dtype=torch.bool)))
assert normal_idle_mask(env).tolist()==[True,False,False,False,False,False]
mean=torch.randn(256,34,device=device,requires_grad=True)
base=DistributionGaussianDiag(mean,torch.full_like(mean,math.log(.075)))
off=torch.zeros(256,device=device);off[:64]=math.log(1/3)
d=apply_noise_offset(base,off)
expected=torch.distributions.Independent(torch.distributions.Normal(mean,torch.where((off<0)[:,None],.025,.075).expand_as(mean)),1)
action=d.sample().detach();logp=d.log_prob(action)
torch.testing.assert_close(logp,expected.log_prob(action),atol=3e-5,rtol=1e-6)
torch.testing.assert_close(d.entropy(),expected.entropy())
g=torch.autograd.grad(logp.sum(),mean,retain_graph=True)[0]
ge=torch.autograd.grad(expected.log_prob(action).sum(),mean)[0]
torch.testing.assert_close(g,ge,atol=.002,rtol=1e-5)
order=torch.randperm(256,device=device)
shuffled=apply_noise_offset(DistributionGaussianDiag(mean[order],base.logstd[order]),off[order])
torch.testing.assert_close((shuffled.log_prob(action[order])-logp[order]).exp(),torch.ones(256,device=device))
shift=mean.detach()+.002
new=apply_noise_offset(DistributionGaussianDiag(shift,base.logstd),off)
kl=.5*((d.mean-new.mean)/new.stddev).square().sum(-1)
ref=torch.distributions.kl_divergence(expected,torch.distributions.Independent(torch.distributions.Normal(shift,new.stddev),1))
torch.testing.assert_close(kl,ref,atol=1e-5,rtol=1e-4)
assert abs(float(kl[:64].mean()/kl[64:].mean())-9)<.001
torch.testing.assert_close(d.mode,base.mode,rtol=0,atol=0)
torch.testing.assert_close(d.stddev[64:],base.stddev[64:],rtol=0,atol=0)
if remote:
    stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(stream):
        for _ in range(3):apply_noise_offset(base,off).log_prob(action)
    torch.cuda.current_stream().wait_stream(stream)
    graph=torch.cuda.CUDAGraph()
    with torch.cuda.graph(graph):captured=apply_noise_offset(base,off).log_prob(action)
    graph.replay();torch.cuda.synchronize();torch.testing.assert_close(captured,logp)
print(json.dumps(dict(passed=True,device=device,allocation={'normal_idle':41,'pushed_idle':62,'other_idle':100,'loco':1845},
    likelihood_gradient_entropy_parity=True,shuffled_ratio_one=True,kl_noise_scaling=True,deterministic_mean_unchanged=True)))
