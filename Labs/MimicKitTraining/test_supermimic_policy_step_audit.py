import unittest
import torch
from supermimic_policy_step_audit import direction_scale, assign_direction


class PolicyStepAuditTest(unittest.TestCase):
    def test_equal_kl_for_different_raw_step_sizes(self):
        # Same output-space displacement, independently of the optimizer's step.
        for coefficient in [.0001, .005, .02]:
            scale = direction_scale(lambda s: coefficient*s*s)
            self.assertLessEqual(coefficient*scale*scale, .05)
            self.assertGreater(coefficient*scale*scale, .04998)

    def test_both_signs_and_finite_search_bound(self):
        scale = direction_scale(lambda s: max(.001*s*s, .003*s*s))
        self.assertLessEqual(.003*scale*scale, .05)
        self.assertEqual(direction_scale(lambda s: 1e-9*s*s), 128.)

    def test_probe_assignment_and_exact_restore(self):
        p = torch.nn.Parameter(torch.tensor([1., -2., 3.]))
        initial = [p.detach().clone()]
        delta = [torch.tensor([.02, -.03, .01])]
        for scale in [4., -4., 0.]:
            assign_direction([p], initial, delta, scale)
            torch.testing.assert_close(p, initial[0]+scale*delta[0], rtol=0, atol=0)
        torch.testing.assert_close(p, initial[0], rtol=0, atol=0)


if __name__ == '__main__':unittest.main()
