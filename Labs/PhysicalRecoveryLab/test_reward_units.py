"""Reward-unit migration must preserve actor parameters and value meaning."""
from types import SimpleNamespace
import torch
from train import rescale_critic_units


def main():
    torch.manual_seed(123)
    actor=torch.nn.Linear(8,4)
    critic=SimpleNamespace(mlp=torch.nn.Sequential(torch.nn.Linear(8,16),torch.nn.Tanh(),torch.nn.Linear(16,1)))
    critic.parameters=critic.mlp.parameters
    optimizer=torch.optim.Adam([*actor.parameters(),*critic.parameters()])
    x=torch.randn(64,8)
    (actor(x).square().mean()+critic.mlp(x).square().mean()).backward();optimizer.step()
    algorithm=SimpleNamespace(actor=actor,critic=critic,optimizer=optimizer)
    a=actor(x).detach().clone();v=critic.mlp(x).detach().clone()
    actor_state={p:{k:t.clone() if torch.is_tensor(t) else t for k,t in optimizer.state[p].items()} for p in actor.parameters()}
    rescale_critic_units(algorithm,1/30)
    assert torch.equal(actor(x),a)
    assert torch.allclose(critic.mlp(x),v/30,atol=1e-8,rtol=1e-5)
    assert all(p not in optimizer.state for p in critic.parameters())
    for p,values in actor_state.items():
        for key,expected in values.items():assert torch.equal(optimizer.state[p][key],expected)
    rescale_critic_units(algorithm,30)
    assert torch.allclose(critic.mlp(x),v,atol=1e-7)
    print('PASS: values retain their physical reward meaning, actor and its optimizer state unchanged, critic moments cleared.')


if __name__=='__main__':main()
