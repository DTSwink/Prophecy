"""Production MSE-only loss and 120-tick termination semantics without a GPU."""
import ast, math
from pathlib import Path
from types import SimpleNamespace
import torch
from perturbed_motion import com2_velocity,com2_failure,tracking_blend
torch.set_num_threads(1)
tree=ast.parse(Path(__file__).with_name('perturbed_omni.py').read_text())
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ['_tracking_losses','_update_done']]
class Base:
    def _tracking_losses(self,*args): return self.base_terms.clone()
    def _update_done(self):
        self._done_buf.copy_(torch.where(self._time_buf>=10.,3,0))
scope=dict(torch=torch,Base=Base,com2_velocity=com2_velocity,com2_failure=com2_failure,tracking_blend=tracking_blend,
    EnvMode=SimpleNamespace(TRAIN=1),DoneFlags=SimpleNamespace(NULL=SimpleNamespace(value=0),FAIL=SimpleNamespace(value=1),SUCC=SimpleNamespace(value=2),TIME=SimpleNamespace(value=3)))
testcls=ast.ClassDef(name='Env',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=methods,decorator_list=[])
exec(compile(ast.fix_missing_locations(ast.Module(body=[testcls],type_ignores=[])),'production_mse_done','exec'),scope)
e=scope['Env']();n=6
e._perturb_ready=True;e._mse_only=True;e._idle_position_getup=True;e._additive_head_reward=False
e._perturbed_rows=torch.tensor([False,False,True,True,True,True])
e._perturbed_ids=torch.where(e._perturbed_rows)[0]
e._prior_ids=torch.empty(0,dtype=torch.long);e._prior=None;e._prior_raw=torch.zeros(n);e._ae_weight=0.
e._perturbed_getup=torch.zeros(n,dtype=torch.bool);e._recovery_rows=e._perturbed_getup
e._gaits=torch.tensor([-1.,0.,-1.,0.,0.,0.]);e._motion_ids=torch.arange(n)
e._tracking_mix=torch.zeros(n);e._time_buf=torch.zeros(n)
e._getup_position_weight=10.;e._mode=0
e.loss_term_names=['position_mse','linear_velocity_mse','rotation_mse','angular_velocity_mse','flat_com_velocity']
e.base_terms=torch.arange(1.,n*5+1).view(n,5)
e._refresh_reward_rotations=lambda:None;e.reward_target_pos=torch.zeros(n,3,3)
p=torch.ones(n,3,3)
for tick in [0,79,80,119]:
    e._time_buf.fill_(tick/30)
    terms=e._tracking_losses(p,p,p,p,p,p)
    torch.testing.assert_close(terms[:,:4],e.base_terms[:,:4])
    assert torch.all(e._tracking_mix==1) and torch.all(terms[:,-1]==0)
    torch.testing.assert_close(terms[:2,4],e.base_terms[:2,4])
    assert torch.all(terms[2:,4]==0)
e._episode_length=10.;e._perturb_cfg=dict(episode_ticks=120,getup_ticks=180,grace_ticks=8,min_speed_ratio=.7,loco_failure_penalty=100.)
e._done_buf=torch.zeros(n,dtype=torch.long);e._reset_reason=e._done_buf.clone()
e._head_id=0;e._head_reset_height=torch.ones(n)*2.;e._com2_ids=torch.arange(3)
e._com2_masses=torch.ones(3)/3;e._com2_targets=torch.tensor([[1.,0.]]).repeat(n,1)
vel=torch.zeros(n,3,3);vel[:,:,0]=1.
e._get_char_id=lambda:0
e._engine=SimpleNamespace(get_body_pos=lambda c:torch.zeros(n,3,3),get_body_vel=lambda c:vel)
e._reward_buf=torch.ones(n)
e._time_buf.fill_(119/30);e._update_done();assert torch.all(e._done_buf==0)
e._time_buf.fill_(120/30);e._update_done();assert e._done_buf.tolist()==[0,0,3,3,3,3]
e._time_buf.fill_(300/30);e._update_done();assert torch.all(e._done_buf==3)
# ±45-degree heading and70..170%speed rules; preserve8-tick grace.
vel[3,:,0]=.69;vel[4,:,0]=1.71;vel[5,:,0]=0.;vel[5,:,1]=1.
for tick,want in [(8,[0]*n),(9,[0,0,0,1,1,1])]:
    e._reward_buf.fill_(1);e._time_buf.fill_(tick/30);e._update_done()
    assert e._done_buf.tolist()==want
    assert e._reward_buf.tolist()==([1]*n if tick==8 else [1,1,1,-99,-99,-99])
print('PASS: full MSE at tick0 onward; no AE call;120-tick perturbed/300-tick normal horizon; original COM2/grace/failure penalty.')
