"""CUDA-graph-safe per-row predictor routing, without evaluating other labels."""
import torch
from torch import nn
from torch.nn import functional as F
from transition_features import MOTION_DIM


class RoutedPrior(nn.Module):
    def __init__(self,priors):
        super().__init__()
        self.names=tuple(sorted(priors))
        values=[priors[name] for name in self.names]
        self.register_buffer('mean',torch.stack([p.mean for p in values]))
        self.register_buffer('std',torch.stack([p.std for p in values]))
        self.layers=[]
        for i,layer in enumerate(values[0].model.projector):
            if any(type(p.model.projector[i]) is not type(layer) for p in values):
                raise ValueError('Predictor architectures differ')
            if isinstance(layer,(nn.Linear,nn.LayerNorm)):
                for field in ('weight','bias'):
                    self.register_buffer(f'layer_{i}_{field}',torch.stack([
                        getattr(p.model.projector[i],field).detach() for p in values]))
            if isinstance(layer,nn.Linear):self.layers.append(('linear',i,None))
            elif isinstance(layer,nn.LayerNorm):
                if any(p.model.projector[i].eps!=layer.eps for p in values):raise ValueError('LayerNorm epsilon mismatch')
                self.layers.append(('norm',i,(layer.normalized_shape,layer.eps)))
            elif isinstance(layer,nn.GELU):self.layers.append(('gelu',i,layer.approximate))
            else:raise ValueError(f'Unsupported predictor layer: {layer}')

    def forward(self,rows,type_ids):
        normalized=(rows-self.mean.index_select(0,type_ids)[:,None])/self.std.index_select(0,type_ids)[:,None]
        x=normalized[...,MOTION_DIM:]
        for kind,i,options in self.layers:
            if kind=='gelu':x=F.gelu(x,approximate=options);continue
            weight=getattr(self,f'layer_{i}_weight').index_select(0,type_ids)
            bias=getattr(self,f'layer_{i}_bias').index_select(0,type_ids)
            if kind=='linear':x=torch.bmm(x,weight.transpose(1,2))+bias[:,None]
            else:
                shape,eps=options
                x=F.layer_norm(x,shape,eps=eps)*weight[:,None]+bias[:,None]
        return (normalized[...,:MOTION_DIM]-x).square().mean(-1)
