"""AMP replay copies the actual rewards across PPO update boundaries."""
import tempfile
from types import SimpleNamespace
import numpy as np
import torch
from observe import AMPTrainingRecorder

class Env:
    _device='cpu'
    _episode_length=2/30
    def __init__(self):
        self._done_buf=torch.zeros(1);self._time_buf=torch.zeros(1);self._reward_buf=torch.zeros(1)
        self._engine=SimpleNamespace(get_obj_body_names=lambda c:['pelvis'],get_timestep=lambda:1/30,
            get_body_pos=lambda c:torch.zeros(1,1,3),get_body_rot=lambda c:torch.tensor([[[0.,0.,0.,1.]]]))
    def _get_char_id(self):return 0
    def step(self,a):self._time_buf+=1/30
    def reset(self,env_ids=None):self._time_buf.zero_()

with tempfile.TemporaryDirectory() as directory:
    env=Env();reward=torch.zeros(1,1)
    buffer=SimpleNamespace(_buffer_head=0,get_data=lambda n:reward)
    agent=SimpleNamespace(_exp_buffer=buffer,_compute_rewards=lambda:None)
    recorder=AMPTrainingRecorder(env,directory,agent,lambda:0)
    env.reset();env.step(None);reward[0]=1.25;agent._compute_rewards()
    env._done_buf[:]=3;env.step(None);reward[0]=2.5;agent._compute_rewards()
    assert recorder.ready
    recorder.finish(1,2)
    with np.load(directory+'/replay.npz') as saved:
        np.testing.assert_allclose(saved['data'][:,2],[0,1.25,2.5])
        np.testing.assert_allclose(saved['loss_terms'][:,0],[0,-1.25,-2.5])
print('PASS: exact per-tick AMP rewards across updates; no extra inference')
