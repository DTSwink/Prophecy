"""Reward accounting and real checkpoint expansion checks; CPU only."""
import os
import sys
import copy
from pathlib import Path
from unittest.mock import patch
os.environ['PYGLET_HEADLESS']='true'
sys.path.insert(0,'/workspace/mimickit_trial/MimicKit/mimickit')
import torch
from head_height import HeadHeightEnv, CharEnv
from resume import append_height_records

torch.set_num_threads(1)
class Engine:
    def get_body_pos(self,char): return self.pos
e=HeadHeightEnv.__new__(HeadHeightEnv)
e._engine=Engine();e._char_ids=[0];e._head_id=1;e._pelvis_id=0
e._peak_height=torch.zeros(2);e._body_peaks=torch.zeros(2,2)
e._timestep_buf=torch.zeros(2,dtype=torch.int);e._episode_steps=45
e._reward_buf=torch.zeros(2);e._done_buf=torch.zeros(2,dtype=torch.int)
total=torch.zeros(2)
for t in range(1,46):
    e._engine.pos=torch.zeros(2,2,3)
    e._engine.pos[0,:,2]=torch.tensor([.2,1.2] if t==8 else [1.1,.4] if t==12 else [.1,.1])
    e._engine.pos[1,:,2]=torch.tensor([.7,.9] if t==45 else [.1,.1])
    e._timestep_buf[:]=t
    e._update_misc();e._update_reward();e._update_done();total+=e._reward_buf
    if t<45: assert not e._reward_buf.any() and not e._done_buf.any()
# Independent peak minimum is 1.1; maximum instantaneous minimum is only .4.
torch.testing.assert_close(total,torch.tensor([1.1,.7]))
assert (e._done_buf==2).all()
with patch.object(CharEnv,'_reset_envs',return_value=None):
    e._reset_envs(torch.tensor([0]))
torch.testing.assert_close(e._body_peaks,torch.tensor([[.1,.1],[.9,.7]]))
with patch.object(CharEnv,'_compute_obs',return_value=torch.zeros(2,140)):
    assert e._compute_obs().shape==(2,144)

root=Path(sys.argv[1])
model=torch.load(root/'model.pt',map_location='cpu',weights_only=True)
state=torch.load(root/'resume_state.pt',map_location='cpu',weights_only=False)
old=copy.deepcopy(model);old_state=copy.deepcopy(state)
append_height_records(model,state)
x=torch.randn(32,142);new_x=torch.cat((x,torch.rand(32,2)),dim=1)
for part in ['actor','critic']:
    key=f'_model._{part}_layers.0.weight'
    torch.testing.assert_close(model[key][:,:142],old[key],rtol=0,atol=0)
    assert not model[key][:,142:].any()
    optimizer=state[f'{part}_optimizer'];first=optimizer['param_groups'][0]['params'][0]
    torch.testing.assert_close(optimizer['state'][first]['momentum_buffer'][:,:142],old_state[f'{part}_optimizer']['state'][first]['momentum_buffer'],rtol=0,atol=0)
    def forward(m,obs):
        v=((obs-m['_obs_norm._mean'])/m['_obs_norm._std']).clamp(-10,10)
        for layer in [0,2]:
            prefix=f'_model._{part}_layers.{layer}'
            v=torch.relu(torch.nn.functional.linear(v,m[prefix+'.weight'],m[prefix+'.bias']))
        prefix='_model._action_dist._mean_net' if part=='actor' else '_model._critic_out'
        return torch.nn.functional.linear(v,m[prefix+'.weight'],m[prefix+'.bias'])
    torch.testing.assert_close(forward(model,new_x),forward(old,x),rtol=1e-5,atol=1e-6)
print('MINIMUM_PEAKS_AND_REAL_CHECKPOINT_MIGRATION_PASS',flush=True)
