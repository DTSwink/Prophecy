"""Isolated PPO advantage-cap ablation; reward and ratio/KL guards unchanged."""
import torch


def clipping_stats(normalized, failures, limit):
    negative=(-normalized).clamp_min(0)
    removed=(negative-limit).clamp_min(0)
    terminal=negative[failures]
    return dict(above4_fraction=float((normalized.abs()>4).float().mean()),
                above_cap_fraction=float((normalized.abs()>limit).float().mean()),
                negative_mass_removed_at4=float((negative-4).clamp_min(0).sum()/negative.sum().clamp_min(1e-12)),
                negative_mass_removed_at_cap=float(removed.sum()/negative.sum().clamp_min(1e-12)),
                terminal_count=int(failures.sum()),
                terminal_negative_mass_removed_at4=float((terminal-4).clamp_min(0).sum()/terminal.sum().clamp_min(1e-12)),
                max_absolute_normalized=float(normalized.abs().max()))


def install(agent, limit):
    """Use upstream target/normalization path and audit its unchanged math."""
    from envs.base_env import DoneFlags
    from util import torch_util
    assert limit>0
    original=agent._build_train_data
    old=float(agent._norm_adv_clip)
    agent._norm_adv_clip=float(limit)
    agent._advantage_audit={}

    def build():
        info=original()
        with torch.no_grad():
            buffer=agent._exp_buffer
            observations=buffer.get_data('obs')
            values=torch_util.eval_minibatch(agent._model.eval_critic,
                {'obs':agent._obs_norm.normalize(observations)},agent._critic_eval_batch_size).squeeze(-1)
            normalized=(buffer.get_data('tar_val')-values-info['adv_mean'])/info['adv_std'].clamp_min(1e-5)
            torch.testing.assert_close(buffer.get_data('adv'),normalized.clamp(-limit,limit),atol=2e-5,rtol=2e-5)
            agent._advantage_audit=clipping_stats(normalized,buffer.get_data('done')==DoneFlags.FAIL.value,limit)
        return info

    agent._build_train_data=build
    return dict(original_limit=old,limit=float(limit),reward_unchanged=True,
                critic_targets_unchanged=True,ppo_ratio_clip_and_kl_guard_unchanged=True)
