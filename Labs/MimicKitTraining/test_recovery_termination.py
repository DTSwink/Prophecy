"""Recovery keeps tracking failures and timeout, permits floor contact."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
import torch
from recovery_omni import RecoveryOmniEnv
from omni_walk import OmniWalkEnv
from envs.base_env import DoneFlags
env=object.__new__(RecoveryOmniEnv)
env._recovery_ready=True;env._device='cpu';env._recovery_ids=torch.tensor([0,1])
env._reset_after_getup=False
env._time_buf=torch.ones(3);env._episode_length=10.;env._motion_ids=torch.zeros(3,dtype=torch.long)
env._done_buf=torch.zeros(3,dtype=torch.int);env._pose_termination=True;env._pose_termination_dist=1.;env._global_obs=True
pos=torch.zeros(3,15,3);rot=torch.tensor([[0.,0.,0.,1.]]).repeat(3,1)
env._ref_body_pos=pos.clone();env._ref_root_rot=rot.clone()
env._engine=SimpleNamespace(get_root_rot=lambda c:rot,get_body_pos=lambda c:pos)
env._get_char_id=lambda:0;env._track_global_root=lambda:False
env._get_motion_times=lambda ids:torch.zeros(len(ids));env._motion_lib=SimpleNamespace(get_motion_length=lambda ids:torch.ones(len(ids)))
env.target_distances_sq=torch.zeros(3,5);env._target_radius_sq=torch.tensor(.27).square()
env._recovery_target_indices=list(range(5))
def floor_fail(self):self._done_buf[:]=DoneFlags.FAIL.value
with patch.object(OmniWalkEnv,'_update_done',floor_fail):
    env._update_done();assert env._done_buf.tolist()==[0,0,DoneFlags.FAIL.value]
    env.target_distances_sq[1,0]=.28**2
    env._update_done();assert env._done_buf.tolist()==[0,DoneFlags.FAIL.value,DoneFlags.FAIL.value]
    env._time_buf[0]=10.;env._update_done();assert env._done_buf[0]==DoneFlags.TIME.value
    env._time_buf[0]=1.;pos[0,3,2]=1.1;env._update_done();assert env._done_buf[0]==DoneFlags.FAIL.value
    pos.zero_();env._reset_after_getup=True
    env.target_distances_sq.zero_();env.recovery_active=lambda:torch.tensor([False,True,False])
    env._update_done();assert env._done_buf.tolist()==[DoneFlags.TIME.value,0,DoneFlags.FAIL.value]
    env.target_distances_sq[0,0]=.28**2
    env._update_done();assert env._done_buf[0]==DoneFlags.FAIL.value
    env._reset_after_getup=False;env._recovery_target_indices=[3,4]
    env.target_distances_sq[:,:3]=.5**2
    env._update_done();assert env._done_buf.tolist()==[0,0,DoneFlags.FAIL.value]
    for foot in (3,4):
        env.target_distances_sq[:,3:]=0;env.target_distances_sq[1,foot]=.28**2
        env._update_done();assert env._done_buf.tolist()==[0,DoneFlags.FAIL.value,DoneFlags.FAIL.value]
    env.target_distances_sq.zero_();pos[0,3,2]=1.1
    env._update_done();assert env._done_buf[0]==DoneFlags.FAIL.value
env._recovery_rows=torch.tensor([True,True,False]);env._recovery_start=torch.tensor([.9,.9,0.])
env._recovery_motion=torch.tensor([0,0,0]);env._time_buf=torch.tensor([.5-2e-7,.5-1e-4,0.])
env._recovery_lib=SimpleNamespace(get_motion_length=lambda ids:torch.full((len(ids),),1.4))
assert RecoveryOmniEnv.recovery_active(env).tolist()==[False,True,False]
print('PASS: recovery-only head/hand exemption; feet, pose failure, clip-end and timeout retained; other rows unchanged')
