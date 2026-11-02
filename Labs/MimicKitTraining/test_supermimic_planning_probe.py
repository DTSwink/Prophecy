import unittest
import torch
from supermimic_planning_probe import elite_distribution, accumulate, residual_scale


class Checks(unittest.TestCase):
    def test_elites_are_selected_per_world_and_population_variance_matches_cem(self):
        candidates=torch.tensor([[[0.,0.],[100.,100.]],[[2.,4.],[102.,104.]],[[8.,10.],[108.,110.]]])
        scores=torch.tensor([[9.,0.],[8.,7.],[0.,9.]])
        mean,std=elite_distribution(candidates,scores,minimum=.02,maximum=10.)
        self.assertTrue(torch.equal(mean,torch.tensor([[1.,2.],[105.,107.]])))
        self.assertTrue(torch.equal(std,torch.tensor([[1.,2.],[3.,3.]])))

    def test_first_terminal_reward_only_and_timeout_not_failure(self):
        active=torch.ones(2,dtype=torch.bool);failed=torch.zeros_like(active)
        total=torch.zeros(2);discounted=torch.zeros(2)
        for tick,(reward,done,fail) in enumerate([
            ([1.,2.],[False,False],[False,False]),
            ([-99.,3.],[True,True],[True,False]),
            ([999.,999.],[False,False],[False,False])]):
            active,failed,total,discounted=accumulate(active,failed,total,discounted,torch.tensor(reward),torch.tensor(done),torch.tensor(fail),tick)
        self.assertEqual(failed.tolist(),[True,False])
        self.assertTrue(torch.equal(total,torch.tensor([-98.,5.])))
        self.assertTrue(torch.allclose(discounted,torch.tensor([1.-.99*99,2.+.99*3])))

    def test_correction_ends_before_the_independent_future_window(self):
        self.assertEqual(residual_scale(0),1.)
        self.assertEqual(residual_scale(7),.125)
        self.assertEqual(residual_scale(8),0.)
        self.assertEqual(residual_scale(119),0.)


if __name__=='__main__':
    unittest.main()
