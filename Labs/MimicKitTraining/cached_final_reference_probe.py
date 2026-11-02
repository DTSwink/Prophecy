"""Cache immutable bank reference frames without changing reset RNG ordering."""
import torch


FIELDS = ('_ref_root_pos', '_ref_root_rot', '_ref_root_vel', '_ref_root_ang_vel',
          '_ref_joint_rot', '_ref_dof_vel', '_ref_dof_pos', '_ref_body_pos', '_ref_body_rot')


class CachedFinalReference:
    def __init__(self, final):
        self.final = final
        self.cache = {}
        e = final.env
        assert final.cfg.get('plus_blended')
        with torch.no_grad():
            for prefix in ['push', 'plus']:
                times = final.bank[prefix+'_motion_time']
                assert times.ndim == 2
                motions, choices = times.shape
                ids = torch.arange(motions, device=e._device).repeat_interleave(choices)
                values = list(e._motion_lib.calc_motion_frame(ids, times.reshape(-1)))
                values.append(e._motion_lib.joint_rot_to_dof(values[4]))
                values.extend(e._kin_char_model.forward_kinematics(values[0], values[1], values[4]))
                self.cache[prefix] = [x.reshape(motions, choices, *x.shape[1:]).contiguous() for x in values]

    def __call__(self, ids):
        f = self.final
        e = f.env
        push = ids[f.pushed[ids]]
        plus = ids[f.plus[ids]]
        # Preserve all three RNG calls, their order, shapes and bounds exactly.
        f.choice[push] = torch.randint(f.bank['push_dof'].shape[1], (len(push),), device=e._device)
        f.choice[plus] = torch.randint(f.bank['plus_dof'].shape[1], (len(plus),), device=e._device)
        f.kick_choice[ids] = torch.randint(len(f.bank['kicks']), (len(ids),), device=e._device)
        f.first_foot[ids] = -1
        f.last_kick[ids] = -1
        f.kick_count[ids] = 0
        f.kick_error[ids] = 0
        f.last_requested[ids] = 0
        for prefix, rows in [('push', push), ('plus', plus)]:
            index = (e._motion_ids[rows], f.choice[rows])
            e._motion_time_offsets[rows] = f.bank[prefix+'_motion_time'][index]
            for field, cached in zip(FIELDS, self.cache[prefix]):
                getattr(e, field)[rows] = cached[index]
