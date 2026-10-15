"""Independent early terminal, delayed reset, reward columns and viewer rows."""
import json,tempfile
from pathlib import Path
from types import SimpleNamespace
import torch,numpy as np
from observe import AMPCohortRecorder
from replay import convert

class Env:
    _device='cpu';_episode_length=4/30
    def __init__(self):
        self._done_buf=torch.zeros(2);self._time_buf=torch.zeros(2);self._reward_buf=torch.zeros(2)
        self._upright_cohort=torch.tensor([False,True]);self._starts_on_back=torch.tensor([True,False])
        self.pos=torch.tensor([[[0.,0.,.1]],[[0.,0.,1.]]])
        self._engine=SimpleNamespace(get_obj_body_names=lambda c:['head'],get_timestep=lambda:1/30,
            get_body_pos=lambda c:self.pos,get_body_rot=lambda c:torch.tensor([[[0.,0.,0.,1.]],[[0.,0.,0.,1.]]]))
    def _get_char_id(self):return 0
    def step(self,a):self._time_buf+=1/30
    def reset(self,env_ids=None):
        ids=torch.arange(2) if env_ids is None else env_ids
        self._time_buf[ids]=0;self._done_buf[ids]=0

with tempfile.TemporaryDirectory() as directory:
    env=Env();reward=torch.zeros(2,2);buffer=SimpleNamespace(_buffer_head=0,get_data=lambda n:reward)
    agent=SimpleNamespace(_exp_buffer=buffer,_compute_rewards=lambda:None)
    recorder=AMPCohortRecorder(env,directory,agent,lambda:0)
    env.reset()
    for tick in range(4):
        buffer._buffer_head=tick%2
        if tick==0:env._done_buf[1]=1
        if tick==3:env._done_buf[0]=3
        env.step(None);reward[tick%2]=torch.tensor([tick+1,10*(tick+1)])
        if tick==0:env.reset(torch.tensor([1]))
        if tick%2==1:agent._compute_rewards()
    assert recorder.ready
    recorder.finish(1,8)
    with np.load(Path(directory)/'replay.npz') as z:
        assert len(z['pose'])==5 and len(z['pose_1'])==2
        np.testing.assert_equal(z['data'][:,2],[0,1,2,3,4])
        np.testing.assert_equal(z['data_1'][:,2],[0,10])
    payload=convert(Path(directory)/'replay.npz',dict(names=['head'],bones=[],shapes=[]),'test')
    assert len(payload['rows'])==2
    assert [r['effective_k'] for r in payload['rows']]==[4,1]
    assert payload['rows'][1]['evaluation']['cohort']=='upright'
    assert payload['rows'][1]['evaluation']['frame_losses']['total']==[0,-10]
    assert payload['rows'][0]['evaluation']['frame_losses']['total']==[0,-1,-2,-3,-4]
    recorder.arm();recorder.suspend();env.reset()
    assert all(not r.enabled and not r.pending for r in recorder.rows)
    recorder.arm();env.reset();assert all(r.enabled for r in recorder.rows)
print('PASS: independent terminal/reset, exact world-specific AMP rewards across updates, two viewer rows, evaluation isolation')
