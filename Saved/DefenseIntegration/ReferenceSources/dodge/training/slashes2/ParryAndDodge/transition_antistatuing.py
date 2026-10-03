"""Candidate-aware denoising energy for GT-derived motion suppression.

No controller rollout is a training example. Seven independent models consume
the existing causal joint row; the policy never receives a defense label.
"""
from functools import lru_cache
from dataclasses import replace
import torch
from torch import nn
from torch.nn import functional as F
from collision_objective import slerp_axes
from transition_agents import native
from transition_features import FEATURE_DIM,MOTION_DIM,SCHEMA

CONTRACT='gt_suppressed_joint_transition_denoising_v1'
ROTATION_STARTS=(3,12,18,28,34,*range(41,101,6),104,110,119,125)


@lru_cache(maxsize=8)
def rotation_ids(device):
    return torch.tensor([[s+i for i in range(6)] for s in ROTATION_STARTS],device=device)


def blend_state(start,end,amount):
    """Native position/scalar interpolation, shortest-arc rotations, no sign fixups."""
    amount=torch.as_tensor(amount,device=start.device,dtype=start.dtype)
    if amount.ndim==1:amount=amount[:,None].expand(-1,2)
    alpha=torch.cat((amount[:,:1].expand(-1,41),amount[:,1:].expand(-1,90)),-1)
    result=start+(end-start)*alpha
    ids=rotation_ids(start.device)
    first=start[:,ids];last=end[:,ids]
    rotations=slerp_axes(native.tl.rotation_6d_to_matrix(first),native.tl.rotation_6d_to_matrix(last),alpha[:,ids[:,0]])
    encoded=rotations[...,:2,:].flatten(-2)
    # Exact endpoints matter for truly stationary GT, even at arbitrary signs.
    encoded=torch.where((alpha[:,ids[:,0]]==0)[...,None],first,encoded)
    encoded=torch.where((alpha[:,ids[:,0]]==1)[...,None],last,encoded)
    encoded=torch.where((first==last).all(-1,keepdim=True),first,encoded)
    return result.index_copy(1,ids.flatten(),encoded.flatten(1))


def suppress(clean,amount,history_amount):
    """Compress next toward current, optionally previous toward current as well."""
    current=clean[:,2*MOTION_DIM:3*MOTION_DIM]
    previous=clean[:,MOTION_DIM:2*MOTION_DIM]
    following=current+clean[:,:MOTION_DIM]
    proposed=blend_state(current,following,amount)
    history=blend_state(current,previous,history_amount)
    return torch.cat((proposed-current,history,current,clean[:,3*MOTION_DIM:]),-1)


class StatueDenoiser(nn.Module):
    def __init__(self,hidden=1024,layers=3):
        super().__init__();network=[];width=FEATURE_DIM
        for _ in range(layers):
            network.extend((nn.Linear(width,hidden),nn.LayerNorm(hidden),nn.GELU()));width=hidden
        last=nn.Linear(width,MOTION_DIM);nn.init.zeros_(last.weight);nn.init.zeros_(last.bias)
        network.append(last);self.correction=nn.Sequential(*network)

    def forward(self,normalized):return self.correction(normalized)


class FrozenStatuePrior(nn.Module):
    def __init__(self,model,mean,std):
        super().__init__();self.model=model.eval().requires_grad_(False)
        if mean.shape!=(FEATURE_DIM,) or std.shape!=(FEATURE_DIM,):raise ValueError('Wrong anti-statuing normalization shape')
        if not bool(torch.isfinite(mean).all() & torch.isfinite(std).all() & (std>0).all()):
            raise ValueError('Invalid anti-statuing normalization')
        self.register_buffer('mean',mean);self.register_buffer('std',std)

    def forward(self,rows):
        shape=rows.shape[:-1];x=((rows-self.mean)/self.std).reshape(-1,FEATURE_DIM)
        return self.model(x).square().mean(-1).reshape(shape)


def load_statue_prior(path,kind,device):
    cp=torch.load(path,map_location=device,weights_only=False);cfg=cp['config']
    if cp['kind']!=CONTRACT or cfg['schema']!=SCHEMA or cfg['type']!=kind:
        raise ValueError('Incompatible anti-statuing prior')
    model=StatueDenoiser(cfg['hidden_dim'],cfg['num_hidden_layers']).to(device)
    model.load_state_dict(cp['model'],strict=True)
    return FrozenStatuePrior(model,cp['mean'].to(device),cp['std'].to(device))


class RoutedStatuePrior(nn.Module):
    """One candidate-aware model per row; labels are loss-only GPU indices."""
    def __init__(self,priors):
        super().__init__();self.names=tuple(sorted(priors));values=[priors[n] for n in self.names]
        self.register_buffer('mean',torch.stack([p.mean for p in values]))
        self.register_buffer('std',torch.stack([p.std for p in values]))
        self.layers=[]
        for i,layer in enumerate(values[0].model.correction):
            if any(type(p.model.correction[i]) is not type(layer) for p in values):
                raise ValueError('Anti-statuing architectures differ')
            if isinstance(layer,(nn.Linear,nn.LayerNorm)):
                for field in ('weight','bias'):
                    self.register_buffer(f'layer_{i}_{field}',torch.stack([
                        getattr(p.model.correction[i],field).detach() for p in values]))
            if isinstance(layer,nn.Linear):self.layers.append(('linear',i,None))
            elif isinstance(layer,nn.LayerNorm):
                if any(p.model.correction[i].eps!=layer.eps for p in values):raise ValueError('LayerNorm epsilon mismatch')
                self.layers.append(('norm',i,(layer.normalized_shape,layer.eps)))
            elif isinstance(layer,nn.GELU):self.layers.append(('gelu',i,layer.approximate))
            else:raise ValueError('Unsupported anti-statuing layer')

    def forward(self,rows,type_ids):
        x=(rows-self.mean.index_select(0,type_ids)[:,None])/self.std.index_select(0,type_ids)[:,None]
        for kind,i,options in self.layers:
            if kind=='gelu':x=F.gelu(x,approximate=options);continue
            weight=getattr(self,f'layer_{i}_weight').index_select(0,type_ids)
            bias=getattr(self,f'layer_{i}_bias').index_select(0,type_ids)
            if kind=='linear':x=torch.bmm(x,weight.transpose(1,2))+bias[:,None]
            else:
                shape,eps=options
                x=F.layer_norm(x,shape,eps=eps)*weight[:,None]+bias[:,None]
        return x.square().mean(-1)


@torch.no_grad()
def calibrate_statue(agent,episode,objective,target):
    """Read-only inference on the exact resumed batch, before graph capture."""
    import math
    from transition_rollout import rollout
    from transition_objective import per_motion_mean
    if not math.isfinite(target) or target<=0:raise ValueError('Positive finite initial loss required')
    result=rollout(agent,episode)
    score=objective.routed_statue(result.predictor_rows,objective.prior_type_ids)
    raw=float(per_motion_mean(score,episode.valid[:,2:]).mean())
    if not math.isfinite(raw) or raw<=1e-9:raise ValueError('Cannot calibrate absent/nonfinite anti-statuing response')
    weight=target/raw
    objective.weights=replace(objective.weights,anti_statuing=weight)
    return dict(raw=raw,weight=weight,target=target,weighted=raw*weight,
        method='exact resumed batch, equal-motion valid-transition mean, before any optimizer update')
