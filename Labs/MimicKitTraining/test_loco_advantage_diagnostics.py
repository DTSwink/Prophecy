"""CPU checks against the pinned production PPO return builder."""
import types

import torch

from test_loco_privileged_critic import Model, baseline_build_train_data
from learning.experience_buffer import ExperienceBuffer
from util import mp_util
from loco_advantage_diagnostics import install
from loco_privileged_critic import install as install_privileged


def make_agent(privileged, batch_size, clip):
    model = Model()
    parameters = list(model._critic_layers.parameters()) + list(model._critic_out.parameters())
    optimizer = torch.optim.AdamW(parameters, lr=1e-4, weight_decay=0.)
    env = types.SimpleNamespace(_perturbed_rows=(torch.arange(128) % 2 == 1),
        _time_buf=torch.zeros(128), _tracking_mix=torch.ones(128))
    buffer = ExperienceBuffer(2, 128, 'cpu')
    agent = types.SimpleNamespace(_model=model, _env=env, _exp_buffer=buffer,
        _critic_optimizer=types.SimpleNamespace(_optimizer=optimizer, _param_list=parameters),
        _critic_eval_batch_size=batch_size, _discount=.99, _td_lambda=.98, _norm_adv_clip=clip,
        _obs_norm=types.SimpleNamespace(normalize=lambda x:x),
        _compute_succ_val=lambda:0., _compute_fail_val=lambda:0., eval=lambda:model.eval(),
        _record_data_pre_step=lambda *args:None, _record_data_post_step=lambda *args:None)
    agent._build_train_data = types.MethodType(baseline_build_train_data, agent)
    if privileged:
        install_privileged(agent)
    obs = torch.randn(2, 128, 154)
    reward = torch.full((2, 128), .5)
    reward[:, 0] = -99.5
    done = torch.zeros((2, 128), dtype=torch.long)
    done[:, 0] = 1
    for name, value in dict(obs=obs, next_obs=obs*.9, reward=reward, done=done,
        rand_action_mask=torch.ones(2,128), critic_context=torch.rand(2,128,3),
        next_critic_context=torch.rand(2,128,3)).items():
        buffer.set_data(name, value)
    return agent


def main():
    torch.set_num_threads(1)
    mp_util.init(0, 1, 'cpu', 6793)
    for privileged in (False, True):
        for batch_size in (0, 1):
            for clip in (4., 10.):
                torch.manual_seed(317)
                agent = make_agent(privileged, batch_size, clip)
                expected = agent._build_train_data()
                targets = agent._exp_buffer.get_data('tar_val').clone()
                advantage = agent._exp_buffer.get_data('adv').clone()
                assert advantage.abs().amax() == clip
                old_weights = {key:value.clone() for key,value in agent._model.state_dict().items()}
                calls = []
                original = agent._model.eval_critic
                def counted(*args, **kwargs):
                    calls.append(1)
                    return original(*args, **kwargs)
                agent._model.eval_critic = counted
                install(agent)
                rng = torch.get_rng_state().clone()
                actual = agent._build_train_data()
                assert len(calls) == (2 if batch_size == 0 else 4), 'Added a critic forward'
                assert torch.equal(rng, torch.get_rng_state())
                assert torch.equal(targets, agent._exp_buffer.get_data('tar_val'))
                assert torch.equal(advantage, agent._exp_buffer.get_data('adv'))
                assert torch.equal(expected['adv_mean'], actual['adv_mean'])
                assert torch.equal(expected['adv_std'], actual['adv_std'])
                for key, value in old_weights.items():
                    assert torch.equal(value, agent._model.state_dict()[key])
                assert float(actual['adv_clip_fraction_at4']) == 1/128
                assert float(actual['adv_clip_fraction_at10']) == 1/128
                assert float(actual['adv_clip_fraction_at4_normal']) == 1/64
                assert float(actual['adv_clip_fraction_at4_perturbed']) == 0.
                assert 0 < actual['adv_removed_l1_fraction_at10'] < actual['adv_removed_l1_fraction_at4'] < 1
                assert actual['adv_unclipped_abs_max'] > 10
                assert agent._model.eval_critic is counted, 'Critic method not restored'
    print('PASS: baseline/privileged × full/chunked critic × clip4/10; exact targets/advantages/weights/RNG, zero extra forwards, correct pre-clipped fractions and tail mass')


if __name__ == '__main__':
    main()
