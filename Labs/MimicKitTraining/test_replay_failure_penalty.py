"""Replay validation must include the recorded locomotion failure cost."""
import unittest
import numpy as np
from replay import convert_arrays


class ReplayPenaltyTest(unittest.TestCase):
    def recording(self, flag, penalty=100.):
        meta=dict(complete_episode=True,names=['pelvis','head'],
                  task='uefn_omni_absolute_walk',loss_term_names=['position_mse'],
                  reward_from_loss='reciprocal_sum',loco_failure_penalty=penalty,
                  generated_unix=1,iteration=100,samples=1000,fps=30,
                  duration_seconds=2/30,terminal_flag=flag)
        pose=np.zeros((3,2,7));pose[:,:,6]=1
        data=np.zeros((3,3));data[1:,2]=.5;data[-1,0]=flag
        if flag==1:data[-1,2]-=100
        return meta,pose,data,np.ones((3,1)),dict(names=meta['names'],bones=[],shapes=[]),'test'

    def test_failure_penalty(self):
        convert_arrays(*self.recording(1))

    def test_timeout_has_no_penalty(self):
        convert_arrays(*self.recording(3))

    def test_missing_penalty_is_still_rejected(self):
        with self.assertRaisesRegex(AssertionError,'Recorded reward'):
            convert_arrays(*self.recording(1,0.))


if __name__=='__main__':
    unittest.main()
