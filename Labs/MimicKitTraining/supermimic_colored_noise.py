"""Isolated CN-PPO sampling adaptation; never installed in production.

Primary implementation: jkbjh/cn-ppo-paper-code, pinned in research/cn-ppo.
Like its ColoredNoiseDist, replace sampling only; retain Gaussian marginal
log probabilities and optimizer. This does not assert trajectory likelihood
ratios are exact for temporally correlated noise. Torch FFT keeps it on GPU.
"""
import types
import torch


def colored_sequence(shape,beta,device='cpu',generator=None):
    """Gaussian power-law spectrum, with analytically unit marginal variance.

No per-sequence centering or rescaling: those would change the intended DC
component and marginal Gaussian distribution. Frequency zero uses1/length.
"""
    length=shape[-1];assert length>=4 and beta>=0
    white=torch.randn(shape,device=device,generator=generator)
    if beta==0:return white
    freq=torch.fft.rfftfreq(length,device=device).clamp_min(1./length)
    scale=freq.pow(-beta/2)
    variance=scale[0].square()+2*scale[1:].square().sum()
    if length%2==0:variance-=scale[-1].square()
    variance/=length
    return torch.fft.irfft(torch.fft.rfft(white)*scale,n=length)/variance.sqrt()


class ColoredSampler:
    def __init__(self,beta,seed,length=1024):
        self.beta=beta;self.seed=seed;self.length=length;self.buffer=None;self.index=length
        self.generator=None;self.calls=0;self.total=None;self.square=None;self.cross=None;self.previous=None;self.items=0;self.pairs=0

    def sample(self,mean,std):
        assert mean.ndim==2
        if self.generator is None:self.generator=torch.Generator(device=mean.device).manual_seed(self.seed)
        if self.buffer is None or self.index>=self.length:
            self.buffer=colored_sequence((*mean.shape,self.length),self.beta,mean.device,self.generator).permute(2,0,1).contiguous()
            self.index=0
        assert self.buffer.shape[1:]==mean.shape
        noise=self.buffer[self.index];self.index+=1;self.calls+=1
        if self.total is None:
            self.total=torch.zeros((),device=mean.device);self.square=self.total.clone();self.cross=self.total.clone()
        self.total+=noise.sum();self.square+=noise.square().sum();self.items+=noise.numel()
        if self.previous is not None:self.cross+=(noise*self.previous).sum();self.pairs+=noise.numel()
        self.previous=noise.clone()
        return mean+std*noise

    def audit(self):
        return dict(beta=self.beta,length=self.length,calls=self.calls,
                    mean=float(self.total/self.items),rms=float((self.square/self.items).sqrt()),
                    lag1_product=float(self.cross/max(1,self.pairs)))


def install(model,beta,seed,length=1024):
    sampler=ColoredSampler(beta,seed,length);original=model.eval_actor
    def evaluate(this,obs):
        dist=original(obs)
        dist.sample=lambda: sampler.sample(dist.mode,dist.stddev)
        return dist
    model.eval_actor=types.MethodType(evaluate,model)
    return sampler
