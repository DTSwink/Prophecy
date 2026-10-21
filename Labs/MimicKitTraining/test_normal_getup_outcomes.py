"""Production counter masks and post-restore exploration override, without GPU."""
import ast
from enum import IntEnum
import json
import math
from pathlib import Path
from types import SimpleNamespace
import torch
from resume import override_fixed_action_noise

class DoneFlags(IntEnum):NULL=0;FAIL=1;SUCC=2;TIME=3
class EnvMode(IntEnum):TRAIN=0;TEST=1
class Base:
    def _update_done(self):pass

tree=ast.parse(Path(__file__).with_name('perturbed_omni.py').read_text())
methods=[n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body
         if isinstance(n,ast.FunctionDef) and n.name in ('_update_done','take_training_outcomes')]
scope=dict(torch=torch,DoneFlags=DoneFlags,EnvMode=EnvMode,Base=Base,
    com2_velocity=lambda *a:torch.zeros(7,2),
    com2_failure=lambda *a:torch.tensor([0,0,0,1,0,0,1],dtype=torch.bool))
node=ast.Module(body=[ast.ClassDef(name='Trial',bases=[ast.Name(id='Base',ctx=ast.Load())],
    keywords=[],body=methods,decorator_list=[])],type_ignores=[])
exec(compile(ast.fix_missing_locations(node),'production-counters','exec'),scope)
e=scope['Trial']();pos=torch.zeros(7,1,3);pos[:,0,2]=torch.tensor([.4,.95,.8,.4,.4,.95,.4])
vars(e).update(_perturb_ready=True,_mode=EnvMode.TRAIN,_time_buf=torch.full((7,),2.),
    _recovery_rows=torch.tensor([1,1,1,0,1,1,0],dtype=torch.bool),
    _perturbed_rows=torch.tensor([0,0,0,0,1,1,1],dtype=torch.bool),
    _perturbed_getup=torch.tensor([0,0,0,0,1,1,0],dtype=torch.bool),_episode_length=10,
    _perturb_cfg=dict(getup_ticks=180,grace_ticks=8,min_speed_ratio=.7,getup_low_head_failure_fraction=.5,
        getup_low_head_failure_tick=60,getup_failure_penalty=100.,loco_failure_penalty=100.,
        normal_getup_failure_penalty=100.,getup_success_value=100.,getup_success_discount=.99),
    _head_id=0,_head_reset_height=torch.full((7,),.9),_idle_head_height=torch.ones(7),
    _motion_ids=torch.arange(7),_gaits=torch.tensor([-1,-1,-1,1,-1,-1,1]),
    _com2_ids=[0],_com2_masses=torch.ones(1),_com2_targets=torch.zeros(7,2),
    _done_buf=torch.tensor([1,2,3,1,0,0,0]),_reset_reason=torch.zeros(7,dtype=torch.long),
    _outcome_ends=torch.zeros(7,dtype=torch.long),_outcome_failures=torch.zeros(7,dtype=torch.long),
    _outcome_head_resets=torch.zeros(7,dtype=torch.long),_reward_buf=torch.ones(7),_get_char_id=lambda:0,
    _engine=SimpleNamespace(get_body_pos=lambda *a:pos,get_body_vel=lambda *a:torch.zeros(7,1,3)))
e._update_done()
got=e.take_training_outcomes()
assert got==dict(loco_failures=1,loco_episodes=1,getup_failures=1,getup_episodes=2,
                 getup_head_resets=1,normal_getup_failures=1,normal_getup_episodes=3),got
assert all(v==0 for v in e.take_training_outcomes().values())
e._mode=EnvMode.TEST;e._update_done()
assert all(v==0 for v in e.take_training_outcomes().values())
logstd=torch.nn.Parameter(torch.full((34,),math.log(.05)),requires_grad=False)
agent=SimpleNamespace(_model=SimpleNamespace(_action_dist=SimpleNamespace(_logstd_net=logstd)))
noise=override_fixed_action_noise(agent,.075)
torch.testing.assert_close(logstd.exp(),torch.full((34,),.075))
print(json.dumps(dict(passed=True,counters=got,normal_failure_percent=100/3,noise=noise['requested'])))
