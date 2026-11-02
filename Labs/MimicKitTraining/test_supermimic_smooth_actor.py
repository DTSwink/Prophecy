import unittest
import torch
from torch import nn
from supermimic_smooth_actor import BetaSiLU, replace_relu, restore_relu, select_beta


class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self._actor_layers = nn.Sequential(nn.Linear(5, 16), nn.ReLU(), nn.Linear(16, 16),
                                          nn.ReLU(), nn.Linear(16, 12), nn.ReLU())
        self.motor = nn.Linear(12, 4)
        self.phase = nn.Linear(12, 2)
        self.critic = nn.Sequential(nn.Linear(5, 8), nn.ReLU(), nn.Linear(8, 1))

    def eval_actor(self, x):
        from types import SimpleNamespace
        mean = self.motor(self._actor_layers(x))
        return SimpleNamespace(mode=mean, stddev=torch.full_like(mean, .075))

    def eval_phase(self, x):
        return self.phase(self._actor_layers(x))


class Checks(unittest.TestCase):
    def test_gradient_matches_real_forward(self):
        # Includes inputs either side of the ReLU kink; no surrogate backward.
        x = torch.tensor([-.5, -.001, 0., .001, .5], dtype=torch.double, requires_grad=True)
        self.assertTrue(torch.autograd.gradcheck(BetaSiLU(8.), (x,)))
        BetaSiLU(8.)(x).sum().backward()
        self.assertAlmostEqual(x.grad[2].item(), .5)

    def test_parameter_and_critic_preservation(self):
        torch.manual_seed(19)
        model = Model(); x = torch.randn(41, 5)
        initial = {k: v.clone() for k, v in model.state_dict().items()}
        identities = [id(p) for p in model.parameters()]
        critic = model.critic(x).detach(); mean = model.eval_actor(x).mode.detach()
        replaced = replace_relu(model._actor_layers, 8.)
        self.assertEqual(len(replaced), 3)
        self.assertEqual(identities, [id(p) for p in model.parameters()])
        self.assertTrue(torch.equal(critic, model.critic(x)))
        self.assertTrue(all(torch.equal(v, initial[k]) for k, v in model.state_dict().items()))
        restore_relu(replaced)
        self.assertTrue(torch.equal(mean, model.eval_actor(x).mode))

    def test_selection_restores_original_and_uses_validation_only_to_reject(self):
        torch.manual_seed(17)
        model = Model(); x = torch.randn(512, 5)
        original = model.eval_actor(x).mode.detach()
        beta, report = select_beta(model, x[:400], x[400:])
        self.assertGreater(beta, 1)
        self.assertLessEqual(report['heldout']['mean_action_kl'], .002)
        self.assertTrue(torch.equal(original, model.eval_actor(x).mode))
        self.assertEqual(sum(isinstance(m, nn.ReLU) for m in model._actor_layers.modules()), 3)


if __name__ == '__main__':
    torch.set_num_threads(2)
    unittest.main()
