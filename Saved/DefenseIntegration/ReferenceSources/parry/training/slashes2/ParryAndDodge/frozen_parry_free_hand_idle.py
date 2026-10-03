"""Free reconstructed wrists follow the authored unarmed idle in parent space."""
import torch
from torch import nn
from frozen_parry_control_smoothness import rotation_vector

CONTRACT = 'reconstructed_free_wrist_parent_idle_geodesic_squared_left_always_right_undrawn_v1'
IDLE_SOURCE = 'walk_run_sword_prep/authored_pruned_npz/walk_omni/M_Neutral_Stand_Idle_Loop.npz'
IDLE_SHA256 = '90137cbd69a18fd521f511e92410b0db418e7054573adf5ed12e56235702e156'
# Frame 0 of the authored UNARMED neutral idle (not sword-holding preparation,
# noisy primer, bind identity, or a predicted hand rot6). Source is already Y-up.
# H_world @ F_world.T, polar-cleaned once in float64. L/R are not interchangeable.
IDLE_LOCAL = (
    ((.999976626857811, -.004448174467907568, -.005192252110334028),
     (-.004577111788212411, .12860851266624046, -.9916848796454725),
     (.005078955183147338, .9916854663721153, .12858514688939426)),
    ((.9965650293259668, .04540104508670314, -.06925956561783676),
     (-.07811022986663445, .2374702957595699, -.9682492709122194),
     (-.027512439272406097, .9703332436523538, .2402008783255893)),
)


class FreeHandIdle(nn.Module):
    def __init__(self, skeleton):
        super().__init__()
        hands = [skeleton.body_names.index('hand_' + s) for s in ('l', 'r')]
        forearms = [skeleton.body_names.index('lowerarm_' + s) for s in ('l', 'r')]
        assert [skeleton.parents[i] for i in hands] == forearms
        self.register_buffer('hands', torch.tensor(hands, dtype=torch.long))
        self.register_buffer('forearms', torch.tensor(forearms, dtype=torch.long))
        self.register_buffer('idle', torch.tensor(IDLE_LOCAL, dtype=torch.float32))

    def forward(self, rotations, drawn):
        # rotations are FINAL FK + baseline/deviation transported world frames.
        # Row-vector convention: local = world_hand @ world_lowerarm.T.
        local = rotations.index_select(2, self.hands) @ rotations.index_select(2, self.forearms).transpose(-1, -2)
        change = local @ self.idle.transpose(-1, -2)
        angle_squared = rotation_vector(change).square().sum(-1)
        free = torch.stack((torch.ones_like(drawn, dtype=torch.bool), ~drawn.bool()), -1)
        # Mean over eligible hands, not over both when one is carrying a sword.
        return torch.where(free[:, None], angle_squared, 0.).sum(-1) / free.sum(-1)[:, None]
