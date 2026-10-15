"""The shared 1024x1024 actor/critic layout, independent of AMP environments."""
import math
import types
import torch

def register_network():
    from learning.nets import net_builder
    def build_net(input_dict, activation):
        size=sum(v.numel() if torch.is_tensor(v) else math.prod(v.shape) for v in input_dict.values())
        layers=[]
        for width in (1024,1024):
            layer=torch.nn.Linear(size,width)
            torch.nn.init.zeros_(layer.bias)
            layers.extend((layer,activation()))
            size=width
        return torch.nn.Sequential(*layers),{}
    net_builder.fc_1024_1024=types.SimpleNamespace(build_net=build_net)
