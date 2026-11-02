"""Function-preserving doubling of the experimental LayerNorm/SiLU dynamics.

Net2Wider-style duplicate units, with cancelling outgoing-weight perturbations
to let replicas receive different gradients. Uniform duplication preserves
LayerNorm statistics too. This changes only the isolated world model.
"""
import copy
import torch
from torch import nn


@torch.no_grad()
def widen_dynamics(network,seed=91074,split_noise=.05):
    linears=[i for i,m in enumerate(network) if isinstance(m,nn.Linear)]
    assert len(linears)==4
    first,last=linears[0],linears[-1]
    width=network[first].out_features
    assert all(network[i].out_features==width for i in linears[:-1])
    assert all(network[i].in_features==width for i in linears[1:])
    generator=torch.Generator(device=network[first].weight.device).manual_seed(seed)
    layers=[]
    for index,layer in enumerate(network):
        if isinstance(layer,nn.Linear):
            inputs=layer.in_features*(2 if index!=first else 1)
            outputs=layer.out_features*(2 if index!=last else 1)
            expanded=nn.Linear(inputs,outputs,bias=layer.bias is not None,
                               device=layer.weight.device,dtype=layer.weight.dtype)
            weights=layer.weight
            if index!=first:
                noise=torch.randn(weights.shape,device=weights.device,dtype=weights.dtype,
                                  generator=generator)*weights.std()*split_noise
                weights=torch.cat((weights*.5+noise,weights*.5-noise),1)
            if index!=last:weights=weights.repeat(2,1)
            expanded.weight.copy_(weights)
            if layer.bias is not None:
                expanded.bias.copy_(layer.bias.repeat(2) if index!=last else layer.bias)
            layers.append(expanded)
        elif isinstance(layer,nn.LayerNorm):
            assert layer.normalized_shape==(width,) and layer.elementwise_affine
            expanded=nn.LayerNorm(width*2,eps=layer.eps,device=layer.weight.device,
                                  dtype=layer.weight.dtype)
            expanded.weight.copy_(layer.weight.repeat(2))
            expanded.bias.copy_(layer.bias.repeat(2));layers.append(expanded)
        else:
            assert isinstance(layer,nn.SiLU)
            layers.append(copy.deepcopy(layer))
    return nn.Sequential(*layers)
