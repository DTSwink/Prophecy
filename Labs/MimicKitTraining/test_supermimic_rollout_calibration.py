import unittest
import torch
from supermimic_rollout_calibration import cohort_step,summarize,expected_step


class CohortTests(unittest.TestCase):
    def test_marginal_return_matches_enumerated_first_failure(self):
        survival=torch.ones(1);failure=torch.zeros(1);returns=torch.zeros(1)
        for timeout in [False,True]:
            survival,failure,returns=expected_step(survival,failure,returns,
                torch.ones(1),torch.tensor([100.]),torch.tensor([.25]),torch.tensor([timeout]))
        # Failure on tick1, failure on tick2, or survive both ticks.
        enumerated=.25*(-99)+.75*.25*(-98)+.75*.75*2
        self.assertEqual(float(returns),enumerated)
        self.assertEqual(float(failure),.25+.75*.25)
        self.assertEqual(float(survival),0)

    def test_terminal_reward_once_and_no_reset_leak(self):
        active=torch.tensor([True,True]);failed=torch.tensor([False,False]);returns=torch.zeros(2)
        active,failed,returns=cohort_step(active,failed,returns,torch.tensor([-99.,1.]),torch.tensor([True,False]),torch.tensor([True,False]))
        active,failed,returns=cohort_step(active,failed,returns,torch.tensor([999.,2.]),torch.tensor([False,False]),torch.tensor([False,True]))
        self.assertEqual(returns.tolist(),[-99.,3.]);self.assertEqual(failed.tolist(),[True,False])
        self.assertFalse(active.any())

    def test_confusion_excludes_inactive_branch_rows(self):
        result=summarize(torch.tensor([True,True,False]),torch.tensor([True,False,True]),
            torch.tensor([False,True,True]),torch.tensor([-99.,1.,999.]),torch.tensor([1.,-99.,-999.]))
        self.assertEqual(result['rows'],2);self.assertEqual(result['false_positive'],1)
        self.assertEqual(result['false_negative'],1);self.assertEqual(result['return_mae'],100.)


if __name__=='__main__':unittest.main()
