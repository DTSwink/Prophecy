"""CPU-only checks of actual done, PPO target and critic-loss methods."""
import ast,json,types
from pathlib import Path
import torch
from enum import IntEnum
class DoneFlags(IntEnum): NULL=0;FAIL=1;SUCC=2;TIME=3
class Base:
    def _update_done(self): pass

def method(path,name):
    tree=ast.parse(Path(path).read_text())
    return next(n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name)
def klass(name,methods,ns):
    node=ast.Module(body=[ast.ClassDef(name=name,bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=methods,decorator_list=[])],type_ignores=[])
    ast.fix_missing_locations(node);exec(compile(node,name,'exec'),ns);return ns[name]
class EnvMode(IntEnum):TRAIN=0;TEST=1
ns=dict(torch=torch,DoneFlags=DoneFlags,EnvMode=EnvMode,Base=Base,com2_velocity=lambda *a:torch.zeros(6,2),com2_failure=lambda *a:torch.zeros(6,dtype=torch.bool))
x=klass('Trial',[method('Labs/MimicKitTraining/perturbed_omni.py',n) for n in ['_update_done','take_training_outcomes']],ns)()
p=torch.zeros(6,1,3);p[:,0,2]=torch.tensor([.4,.4,.5,.501,.4,.91])
vars(x).update(_perturb_ready=True,_time_buf=torch.tensor([59,60,60,60,60,60])/30,_perturbed_getup=torch.tensor([1,1,1,1,0,1],dtype=torch.bool),_perturbed_rows=torch.tensor([1,1,1,1,0,1],dtype=torch.bool),_episode_length=6,_perturb_cfg=dict(getup_ticks=180,grace_ticks=8,min_speed_ratio=.7,getup_low_head_failure_fraction=.5,getup_low_head_failure_tick=60,getup_failure_penalty=100.),_head_id=0,_head_reset_height=torch.tensor([.9]),_idle_head_height=torch.tensor([1.]),_motion_ids=torch.zeros(6,dtype=torch.long),_gaits=torch.tensor([-1]),_com2_ids=[0],_com2_masses=torch.ones(1),_com2_targets=torch.zeros(1,2),_done_buf=torch.zeros(6,dtype=torch.long),_reset_reason=torch.zeros(6,dtype=torch.long),_reward_buf=torch.ones(6),_get_char_id=lambda:0,_engine=types.SimpleNamespace(get_body_pos=lambda *a:p,get_body_vel=lambda *a:torch.zeros(6,1,3)))
x._mode=EnvMode.TRAIN
x._outcome_ends=torch.zeros(6,dtype=torch.long);x._outcome_failures=torch.zeros_like(x._outcome_ends);x._outcome_head_resets=torch.zeros_like(x._outcome_ends)
x._update_done();assert x._done_buf.tolist()==[0,1,1,0,0,3];assert x._reward_buf.tolist()==[1,-99,-99,1,1,1]

r=x.take_training_outcomes();assert r==dict(loco_failures=0,loco_episodes=0,getup_failures=2,getup_episodes=3,getup_head_resets=1),r
assert not any(x.take_training_outcomes().values())
x._mode=EnvMode.TEST;x._update_done();assert not any(x.take_training_outcomes().values())
# Explicit all-failure, success/timeout, zero completed interval and cohort counts.
x._mode=EnvMode.TRAIN;x._perturbed_getup[:]=False;x._perturbed_getup[0]=True;x._gaits=torch.tensor([-1,1]);x._motion_ids[1]=1
x._outcome_ends[0]=10;x._outcome_failures[0]=3;x._outcome_ends[1]=20;x._outcome_failures[1]=4
r=x.take_training_outcomes();assert r['getup_episodes']==10 and r['getup_failures']==3 and r['loco_episodes']==20 and r['loco_failures']==4
print('Training counters passed: failure/reset separation, eval excluded, read clears interval, separate locomotion/getup denominators.')
# COM2 failure cost applies only to perturbed locomotion, after grace.
x._perturb_cfg['loco_failure_penalty']=100.
x._motion_ids=torch.tensor([1,1,1,1,0,0])
x._perturbed_rows=torch.tensor([1,1,0,1,1,1],dtype=torch.bool)
x._perturbed_getup=torch.tensor([0,0,0,0,0,1],dtype=torch.bool)
x._time_buf=torch.tensor([9,8,9,180,180,60])/30
x._head_reset_height=torch.tensor([.9,.9]);x._idle_head_height=torch.tensor([1.,1.])
x._com2_targets=torch.zeros(2,2)
ns['com2_failure']=lambda *a:torch.tensor([1,1,1,0,1,0],dtype=torch.bool)
x._done_buf.zero_();x._reward_buf.fill_(1.)
x._update_done()
assert x._done_buf.tolist()==[1,0,0,3,3,3],x._done_buf
assert x._reward_buf.tolist()==[-99,1,1,1,1,1],x._reward_buf
# The next transition starts with its own reward; the cost does not persist.
ns['com2_failure']=lambda *a:torch.zeros(6,dtype=torch.bool)
x._time_buf.zero_();x._reward_buf.fill_(1.);x._update_done()
assert x._reward_buf.tolist()==[1]*6
print('Locomotion penalty passed: failure only, grace respected, normal/idle/reset/timeout unchanged, no carryover.')
