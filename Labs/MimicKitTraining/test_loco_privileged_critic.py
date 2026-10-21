"""CPU verification of the isolated privileged-critic sweep helper."""
import ast
import copy
import enum
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Saved/MimicKitLocomotion/research-20261021/pinned_source/MimicKit/mimickit'))
from learning.experience_buffer import ExperienceBuffer
stub = ModuleType('envs.base_env')
stub.DoneFlags = enum.Enum('DoneFlags', {'NULL':0, 'FAIL':1, 'SUCC':2, 'TIME':3})
sys.modules['envs.base_env'] = stub
from learning import rl_util
from util import mp_util, torch_util
from loco_privileged_critic import install

source = Path(sys.path[0])/'learning/ppo_agent.py'
tree = ast.parse(source.read_text())
method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == '_build_train_data')
namespace = dict(torch=torch, base_env=stub, rl_util=rl_util, mp_util=mp_util, torch_util=torch_util)
exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
baseline_build_train_data = namespace['_build_train_data']


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self._actor_layers = torch.nn.Linear(154, 34)
        self._critic_layers = torch.nn.Sequential(torch.nn.Linear(154, 8), torch.nn.ReLU())
        self._critic_out = torch.nn.Linear(8, 1)

    def eval_critic(self, obs):
        return self._critic_out(self._critic_layers(obs))


def main():
    torch.set_num_threads(1)
    mp_util.init(0, 1, 'cpu', 6793)
    model = Model()
    parameters = list(model._critic_layers.parameters()) + list(model._critic_out.parameters())
    optimizer = torch.optim.AdamW(parameters, lr=1e-4, weight_decay=0.)
    optimizer.zero_grad()
    model.eval_critic(torch.randn(4, 154)).square().mean().backward()
    optimizer.step()
    saved_state = copy.deepcopy(optimizer.state_dict())
    actor_before = copy.deepcopy(model._actor_layers.state_dict())
    obs = torch.randn(2, 4, 154)
    value_before = model.eval_critic(obs).detach()
    environment = SimpleNamespace(_perturbed_rows=torch.tensor([False, True, True, False]),
        _time_buf=torch.tensor([0., 0., 1., 2.]), _tracking_mix=torch.tensor([1., 0., 0., 1.]))
    buffer = ExperienceBuffer(2, 4, 'cpu')
    agent = SimpleNamespace(_model=model, _env=environment, _exp_buffer=buffer,
        _critic_optimizer=SimpleNamespace(_optimizer=optimizer, _param_list=parameters),
        _critic_eval_batch_size=0, _discount=.99, _td_lambda=.98, _norm_adv_clip=4.,
        _obs_norm=SimpleNamespace(normalize=lambda x:x),
        _compute_succ_val=lambda:0., _compute_fail_val=lambda:0., eval=lambda:model.eval())

    def pre(observation, info, action, action_info):
        buffer.record('obs', observation)
        buffer.record('rand_action_mask', torch.ones(4))

    def post(observation, reward, done, info):
        for key, data in (('next_obs', observation), ('reward', reward), ('done', done)):
            buffer.record(key, data)
    agent._record_data_pre_step, agent._record_data_post_step = pre, post
    rng = torch.get_rng_state().clone()
    receipt = install(agent)
    assert torch.equal(rng, torch.get_rng_state()), 'Installation consumed RNG'
    assert torch.equal(value_before, model.eval_critic(obs, torch.randn(2, 4, 3)))
    for key, value in actor_before.items():
        assert torch.equal(value, model._actor_layers.state_dict()[key])
    for key, values in saved_state['state'].items():
        for name, value in values.items():
            assert torch.equal(value, optimizer.state_dict()['state'][key][name])
    assert optimizer.param_groups[0]['lr'] == optimizer.param_groups[1]['lr'] == 1e-4

    for tick in range(2):
        agent._record_data_pre_step(obs[tick], {}, None, {})
        environment._time_buf += 1/30
        agent._record_data_post_step(obs[tick]*.9, torch.tensor([1., -99., .5, .5]),
            torch.tensor([0, 1, 3, 0]), {})
        buffer.inc()
    assert torch.allclose(buffer.get_data('next_critic_context')[...,1] -
                          buffer.get_data('critic_context')[...,1], torch.full((2,4), 1/120))
    baseline_info = baseline_build_train_data(agent)
    baseline_targets = buffer.get_data('tar_val').clone()
    baseline_adv = buffer.get_data('adv').clone()
    agent._build_train_data()
    assert torch.equal(baseline_targets, buffer.get_data('tar_val'))
    assert torch.equal(baseline_adv, buffer.get_data('adv'))
    assert torch.equal(buffer.get_data('tar_val')[:,1], torch.full((2,), -99.)), 'Failure bootstrapped'
    batch = buffer.sample(8)
    optimizer.zero_grad()
    agent._compute_critic_loss(batch)['critic_loss'].backward()
    assert model._loco_critic_context.weight.grad.abs().sum() > 0
    optimizer.step()
    assert model._loco_critic_context.weight.abs().sum() > 0
    # Checkpoints/snapshots contain the new weights automatically, actor untouched.
    assert '_loco_critic_context.weight' in model.state_dict()
    for key, value in actor_before.items():
        assert torch.equal(value, model._actor_layers.state_dict()[key])
    print('PASS: exact initial actor/critic parity, RNG and old Adam preserved, pre/post context aligned, TD-lambda parity, failure bootstrap, new critic gradients', receipt)


if __name__ == '__main__':
    main()
