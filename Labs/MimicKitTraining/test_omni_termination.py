"""Boundary, point-offset and failure-priority tests; no physics or training."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
import torch
from unittest.mock import patch
from omni_walk import centre_distances, OmniWalkEnv
from absolute_walk import AbsoluteWalkEnv
from envs.base_env import DoneFlags

p=torch.zeros((7,5,3));q=torch.zeros((7,5,4));q[...,3]=1
target=p.clone();offset=torch.zeros((5,3))
for i in range(5):p[i,i,0]=.27001
p[5,0,0]=.27;p[6,0,0]=.26999
d=centre_distances(p,q,target,q,offset)
assert (d>torch.tensor(.27).square()).any(-1).tolist()==[True]*5+[False,False]
env=object.__new__(OmniWalkEnv);env._termination_ids=torch.arange(5);env._termination_offsets=offset
env.target_radius_m=.27;env.target_distances_sq=torch.zeros_like(d)
env._target_radius_sq=torch.tensor(.27).square()
env.reward_target_pos=target;env.reward_target_rot=q;env._time_buf=torch.ones(7)
env._done_buf=torch.full((7,),DoneFlags.TIME.value);env._get_char_id=lambda:0
class Engine:
    def get_body_pos(self,c):return p
    def get_body_rot(self,c):return q
env._engine=Engine()
with patch.object(AbsoluteWalkEnv,'_update_done',lambda self:None):env._update_done()
assert env._done_buf.tolist()==[DoneFlags.FAIL.value]*5+[DoneFlags.TIME.value]*2
# A head can exceed the sphere by rotation around its neck, with origins equal.
p.zero_();offset[0,0]=.2;turned=q.clone();turned[:,0]=torch.tensor([0.,0.,1.,0.])
d=centre_distances(p,turned,target,q,offset)
torch.testing.assert_close(d[:,0],torch.full((7,),.16))
print('PASS: five independent points; strict 27cm boundary; failure over timeout; rotation offsets')
