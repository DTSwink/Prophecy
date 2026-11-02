import unittest
import torch
from supermimic_uncertain_planner import max_disagreement,calibrate


class Checks(unittest.TestCase):
    def test_disagreement_is_translation_invariant_max_distance(self):
        states=torch.tensor([[[1.,0.]],[[3.,0.]],[[8.,0.]]])
        expected=(states-states.mean(0)).norm(dim=-1).max(0).values
        self.assertTrue(torch.equal(max_disagreement(states),expected))
        self.assertTrue(torch.equal(max_disagreement(states+10),expected))
        self.assertEqual(float(max_disagreement(states[:1])),0)

    def test_calibration_uses_only_training_worlds_and_relative_scores(self):
        u=torch.tensor([[1.,2.,3.,4.],[2.,3.,4.,5.],[4.,5.,6.,7.]])
        actual=torch.tensor([[5.,5.,5.,5.],[6.,6.,6.,6.],[4.,4.,4.,4.]])
        pred=actual+2*u+100
        train=torch.tensor([True,True,False,False])
        out=calibrate(pred,actual,u,train)
        self.assertAlmostEqual(out['coefficient'],2.)
        changed=actual.clone();changed[:,~train]=torch.randn(3,2)*1000
        self.assertEqual(calibrate(pred,changed,u,train)['coefficient'],out['coefficient'])
        self.assertEqual(out['splits']['heldout']['adjusted_relative_optimism_mae'],0)
        self.assertGreater(out['splits']['heldout']['adjusted_selected_true_score'],out['splits']['heldout']['raw_selected_true_score'])
        self.assertEqual(calibrate(actual-2*u,actual,u,train)['coefficient'],0)


if __name__=='__main__':unittest.main()
