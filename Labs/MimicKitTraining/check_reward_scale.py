"""CPU-only algebra check using saved rewards and upstream PPO loss functions.

This tests scaling, not learning performance or the live trainer's gradients.
No policy/optimizer/physics state is changed and no checkpoint is written.
"""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PYGLET_HEADLESS'] = 'true'
import argparse
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import zipfile
import numpy as np
import torch

root = Path('/workspace/mimickit_trial')
sys.path.insert(0, str(root/'MimicKit/mimickit'))
from learning.ppo_agent import PPOAgent
from learning.rl_util import compute_td_lambda_return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    torch.set_num_threads(1)
    with zipfile.ZipFile(args.checkpoint) as z:
        clip = np.load(io.BytesIO(z.read('replay.npz')))
        reward = torch.tensor(clip['data'][1:, 2].copy())[:, None]
    done = torch.zeros_like(reward, dtype=torch.long)
    done[-1] = 2
    zero = torch.zeros_like(reward)
    returns = compute_td_lambda_return(reward, zero, done, .99, .95).flatten()
    big_returns = compute_td_lambda_return(45*reward, zero, done, .99, .95).flatten()

    def normalize(x):
        return ((x-x.mean())/x.std().clamp_min(1e-5)).clamp(-4, 4)

    adv = normalize(returns)
    big_adv = normalize(big_returns)
    torch.testing.assert_close(big_adv, adv, atol=2e-6, rtol=2e-6)

    # Exercise actual upstream actor/critic losses on a controlled CPU model.
    # Model and actions are synthetic; reward sequence is a recorded real episode.
    theta = torch.nn.Parameter(torch.tensor(.01))
    prediction = torch.nn.Parameter(torch.tensor(0.))
    obs = torch.linspace(-1, 1, len(returns))[:, None]
    def actor(x):
        return torch.distributions.Independent(torch.distributions.Normal(theta*x, .05), 1)
    context = SimpleNamespace(
        _obs_norm=SimpleNamespace(normalize=lambda x:x),
        _a_norm=SimpleNamespace(normalize=lambda x:x),
        _model=SimpleNamespace(eval_actor=actor, eval_critic=lambda x:prediction.expand(len(x), 1)),
        _ppo_clip_ratio=.2, _action_bound_weight=0., _action_entropy_weight=0., _action_reg_weight=0.)
    generator = torch.Generator().manual_seed(203)
    action = .01*obs + .05*torch.randn(obs.shape, generator=generator)
    old_logp = actor(obs).log_prob(action).detach()
    batch = dict(obs=obs, action=action, a_logp=old_logp, rand_action_mask=torch.ones(len(obs)))
    actor_grads = []
    critic_grads = []
    critic_losses = []
    for a, target in [(adv, returns), (big_adv, big_returns)]:
        loss = PPOAgent._compute_actor_loss(context, dict(batch, adv=a))['actor_loss']
        actor_grads.append(float(torch.autograd.grad(loss, theta)[0]))
        loss = PPOAgent._compute_critic_loss(context, dict(batch, tar_val=target))['critic_loss']
        critic_losses.append(float(loss))
        critic_grads.append(float(torch.autograd.grad(loss, prediction)[0]))
    assert abs(actor_grads[1]-actor_grads[0]) < 2e-5
    assert abs(critic_grads[1]/critic_grads[0]-45) < 1e-4
    assert abs(critic_losses[1]/critic_losses[0]-2025) < .01

    # Consistently scaling nonzero values AND rewards also cancels after
    # advantage normalization. Reward-only scaling need not cancel.
    values = torch.linspace(-.3, -.01, len(reward))[:, None]
    next_values = torch.cat((values[1:], values[-1:]*0), dim=0)
    a = compute_td_lambda_return(reward, next_values, done, .99, .95)-values
    b = compute_td_lambda_return(45*reward, 45*next_values, done, .99, .95)-45*values
    torch.testing.assert_close(normalize(a), normalize(b), atol=2e-5, rtol=2e-5)
    reward_only = compute_td_lambda_return(45*reward, next_values, done, .99, .95)-values
    report = dict(passed=True, device='cpu', checkpoint=str(args.checkpoint),
        scope='Scaling identities with saved real rewards and controlled synthetic actor/critic; not a learning A/B',
        actor_gradient=actor_grads, actor_gradient_abs_difference=abs(actor_grads[1]-actor_grads[0]),
        critic_gradient_ratio=critic_grads[1]/critic_grads[0], critic_loss_ratio=critic_losses[1]/critic_losses[0],
        consistent_nonzero_critic_scale_cancels=True,
        reward_only_with_fixed_critic_normalized_adv_max_difference=float((normalize(a)-normalize(reward_only)).abs().max()))
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
