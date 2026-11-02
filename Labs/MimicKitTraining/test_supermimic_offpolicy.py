import unittest
import types
import torch
from torch import nn
from supermimic_offpolicy import scalar_distribution, nstep, policy_action, regularized_actor_objective
from vendor.holosoma_fast_sac import Critic


class OffpolicyTests(unittest.TestCase):
    def test_behavior_objective_is_reward_scale_invariant_and_anchors_actions(self):
        action = torch.tensor([[.3, .2], [.1, -.4]], requires_grad=True)
        behavior = torch.zeros_like(action)
        q = action[:, 0]*3+20
        loss, _, _ = regularized_actor_objective(q, action, behavior, 2.5)
        scaled, _, _ = regularized_actor_objective(100*q, action, behavior, 2.5)
        torch.testing.assert_close(loss, scaled)
        first = torch.autograd.grad(loss, action, retain_graph=True)[0]
        second = torch.autograd.grad(scaled, action)[0]
        torch.testing.assert_close(first, second)
        # The dimension irrelevant to Q must move toward the observed action.
        torch.testing.assert_close(first[:, 1], 2*action[:, 1]/action.numel())

    def test_scalar_support_preserves_negative_penalty_and_integer_atoms(self):
        support = torch.linspace(-105, 105, 201)
        values = torch.tensor([-105., -100., 0., 53.2, 105.])
        p = scalar_distribution(values, support)
        torch.testing.assert_close(p.sum(-1), torch.ones(5))
        torch.testing.assert_close((p*support).sum(-1), values, atol=2e-5, rtol=1e-6)
        self.assertTrue(bool((p >= 0).all()))

    def test_nstep_failure_does_not_cross_reset(self):
        rewards = torch.tensor([[1., 1.], [-99., 2.], [500., 3.]])
        done = torch.tensor([[False, False], [True, False], [False, False]])
        fail = done.clone()
        reward, boot, discount, idx = nstep(rewards, done, fail)
        torch.testing.assert_close(reward, torch.tensor([1-.99*99, 1+.99*2+.99**2*3]))
        torch.testing.assert_close(boot, torch.tensor([0., 1.]))
        torch.testing.assert_close(discount, torch.tensor([.99**2, .99**3]))
        self.assertEqual(idx.tolist(), [1, 2])

    def test_timeout_bootstraps_pre_reset_state_not_next_episode(self):
        reward, boot, discount, idx = nstep(torch.tensor([[2.], [999.], [999.]]),
            torch.tensor([[True], [False], [False]]), torch.zeros(3, 1, dtype=torch.bool))
        self.assertEqual(idx.item(), 0)
        self.assertEqual(reward.item(), 2)
        self.assertEqual(boot.item(), 1)
        torch.testing.assert_close(reward+boot*discount*torch.tensor([10.]), torch.tensor([11.9]))

    def test_official_critic_terminal_projection_has_no_bootstrap(self):
        q = Critic({'o': {'start': 0, 'end': 3, 'size': 3}}, ['o'], 2, 201, -105, 105, 32)
        obs = torch.randn(4, 3)
        action = torch.randn(4, 2)
        reward = torch.tensor([-99., -100., 0., 1.])
        p = q.projection(obs, action, reward, torch.zeros(4), torch.full((4,), .99))
        torch.testing.assert_close(p.sum(-1), torch.ones(2, 4))
        torch.testing.assert_close(q.get_value(p), reward.expand(2, 4), atol=3e-5, rtol=1e-6)

    def test_phase_is_a_differentiable_action_only_when_used_by_task(self):
        class Model(nn.Module):
            def __init__(self):
                super().__init__()
                self.motor = nn.Parameter(torch.tensor([[.2, -.1]]))
                self.phase = nn.Parameter(torch.tensor([[.8, .2]]))
            def eval_actor(self, obs):
                return types.SimpleNamespace(mode=self.motor.expand(len(obs), -1))
            def eval_phase(self, obs):
                return self.phase.expand(len(obs), -1)
        model = Model()
        qa, phase, mean = policy_action(model, torch.zeros(2, 3), torch.tensor([False, True]),
            torch.tensor([[1., 0.], [1., 0.]]), torch.tensor([-1., -1.]), torch.tensor([1., 1.]))
        torch.testing.assert_close(qa[:, :2], mean)
        torch.testing.assert_close(qa[0, -2:], torch.zeros(2))
        torch.testing.assert_close(qa[1, -2:].norm(), torch.tensor(1.))
        gradient = torch.autograd.grad(qa[1, -1], model.phase)[0]
        self.assertGreater(float(gradient.abs().sum()), 0)
        with torch.no_grad():
            model.phase.zero_()
        qa, _, _ = policy_action(model, torch.zeros(2, 3), torch.ones(2, dtype=torch.bool),
            torch.tensor([[1., 0.], [0., 1.]]), -torch.ones(2), torch.ones(2))
        torch.testing.assert_close(qa[:, -2:], torch.eye(2))


if __name__ == '__main__':
    unittest.main()
