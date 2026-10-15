"""Local CPU tests: reference phase, loop travel, and rejection of wrong poses."""
import unittest
import numpy as np
from replay_reference import walking_motion, recover_walk_reference


class ReferenceTests(unittest.TestCase):
    def test_phase_and_loop_and_mismatch(self):
        torch, model, motion = walking_motion()
        meta = {'names': model.get_body_names()}
        for start in [0., .123, .517, 1.02]:
            times = torch.arange(65, dtype=torch.float32) / 30 + start
            r, q, _, _, j, _ = motion.calc_motion_frame(torch.zeros(65, dtype=torch.long), times)
            p, b = model.forward_kinematics(r, q, j)
            pose = np.concatenate([p.numpy(), b.numpy()], axis=-1)
            data = np.zeros((65, 3), np.float32)
            data[:, 1] = np.arange(65) / 30
            found = recover_walk_reference(meta, pose, data, 'test_walk')
            self.assertIsNotNone(found)
            np.testing.assert_allclose(found[0], pose, atol=3e-6)
            wrong = pose.copy()
            wrong[0, 2, 2] += .01
            self.assertIsNone(recover_walk_reference(meta, wrong, data, 'test_walk'))
        self.assertIsNone(recover_walk_reference({'task': 'world_pose_mse'}, pose, data, 'test_walk'))


if __name__ == '__main__':
    unittest.main()
