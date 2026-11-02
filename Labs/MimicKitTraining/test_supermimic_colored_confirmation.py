import unittest
import numpy as np
from analyze_supermimic_colored_confirmation import elapsed_curve,compare_curves


class Checks(unittest.TestCase):
    def events(self):
        return [dict(time=t,data=d) for t,d in [
            (10,'WORKER_STARTED white_1 gpu 0\n'),
            (45,'[white_1] STUDENT_BASELINE {"noisy":20}\n'),
            (60,'[colored_1] STUDENT_CHECK {"noisy":1}\n'),
            (115,'[white_1] STUDENT_CHECK {"noisy":18}\n'),
            (210,'[white_1] STUDENT_COMPLETE {"noisy":17}\n')]]

    def test_wall_clock_includes_setup_and_ignores_other_arm(self):
        actual=elapsed_curve(self.events(),'white_1',20)
        np.testing.assert_array_equal(actual,[[0,20],[35,20],[105,18],[200,17]])

    def test_incomplete_or_ambiguous_worker_is_rejected(self):
        with self.assertRaises(AssertionError):elapsed_curve(self.events()[:-1],'white_1',20)
        with self.assertRaises(AssertionError):elapsed_curve(self.events()+self.events()[:1],'white_1',20)

    def test_equal_learning_with_slower_setup_is_not_a_wallclock_gain(self):
        fast=np.array([[0,20],[10,20],[20,10]],dtype=float)
        slow=np.array([[0,20],[20,20],[30,10]],dtype=float)
        comparison=compare_curves(fast,slow)
        self.assertEqual(comparison['common_learning_seconds'],20)
        self.assertGreater(comparison['mean_failure_difference_pp'],0)


if __name__=='__main__':unittest.main()
