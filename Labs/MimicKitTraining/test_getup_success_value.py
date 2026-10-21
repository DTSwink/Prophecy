"""Exercise production done logic and deployed PPO targets without a simulator."""
import ast,io,json,types,zipfile
from pathlib import Path
import torch
from enum import IntEnum
from backup import verified_readback
from botocore.exceptions import ReadTimeoutError

class DoneFlags(IntEnum):NULL=0;FAIL=1;SUCC=2;TIME=3
class Base:
    def _update_done(self):pass
class EnvMode(IntEnum):TRAIN=0;TEST=1
def methods(text,names):
    tree=ast.parse(text)
    return [n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name in names]
scope=dict(torch=torch,DoneFlags=DoneFlags,EnvMode=EnvMode,Base=Base,
    com2_velocity=lambda *a:torch.zeros(6,2),com2_failure=lambda *a:torch.zeros(6,dtype=torch.bool))
node=ast.Module(body=[ast.ClassDef(name='Trial',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],
    body=methods(Path('Labs/MimicKitTraining/perturbed_omni.py').read_text(),['_update_done']),decorator_list=[])],type_ignores=[])
exec(compile(ast.fix_missing_locations(node),'env','exec'),scope)
e=scope['Trial']();pos=torch.zeros(6,1,3);pos[:,0,2]=torch.tensor([.91,.85,.4,.91,.91,.4])
vars(e).update(_perturb_ready=True,_mode=EnvMode.TEST,_time_buf=torch.tensor([20,180,60,20,0,59])/30,
    _perturbed_getup=torch.tensor([1,1,1,0,1,1],dtype=torch.bool),
    _perturbed_rows=torch.tensor([1,1,1,0,1,1],dtype=torch.bool),_episode_length=6,
    _perturb_cfg=dict(getup_ticks=180,grace_ticks=8,min_speed_ratio=.7,getup_low_head_failure_fraction=.5,
        getup_low_head_failure_tick=60,getup_failure_penalty=100.,getup_success_value=100.,getup_success_discount=.99),
    _head_id=0,_head_reset_height=torch.tensor([.9]),_idle_head_height=torch.tensor([1.]),
    _motion_ids=torch.zeros(6,dtype=torch.long),_gaits=torch.tensor([-1]),
    _com2_ids=[0],_com2_masses=torch.ones(1),_com2_targets=torch.zeros(1,2),
    _done_buf=torch.tensor([0,0,0,2,0,0]),_reset_reason=torch.zeros(6,dtype=torch.long),
    _reward_buf=torch.full((6,),.8),_get_char_id=lambda:0,
    _engine=types.SimpleNamespace(get_body_pos=lambda *a:pos,get_body_vel=lambda *a:torch.zeros(6,1,3)))
e._update_done()
assert e._done_buf.tolist()==[2,3,1,2,0,0]
torch.testing.assert_close(e._reward_buf,torch.tensor([99.8,.8,-99.2,.8,.8,.8]))
# Normal get-up failures receive the same cost, without touching completion,
# timeout, locomotion, or charging perturbed failures twice.
saved=vars(e).copy()
vars(e).update(_perturb_cfg=dict(e._perturb_cfg,normal_getup_failure_penalty=100.),
    _recovery_rows=torch.tensor([1,1,1,0,1,1],dtype=torch.bool),
    _perturbed_rows=torch.tensor([0,0,0,0,1,1],dtype=torch.bool),
    _perturbed_getup=torch.tensor([0,0,0,0,1,1],dtype=torch.bool),
    _time_buf=torch.tensor([60,60,180,60,60,60])/30,
    _done_buf=torch.tensor([1,2,3,1,0,0]),_reward_buf=torch.full((6,),.8))
e._update_done()
torch.testing.assert_close(e._reward_buf,torch.tensor([-99.2,.8,.8,.8,99.8,-99.2]))
assert e._done_buf.tolist()==[1,2,3,1,2,1]
vars(e).update(saved)
# Run upstream target construction and critic loss, including next-episode isolation.
with zipfile.ZipFile('Saved/MimicKitEquipment/getup-skew-source.zip') as z:
    util=ast.parse(z.read('MimicKit/mimickit/learning/rl_util.py').decode())
    scope.update(base_env=types.SimpleNamespace(DoneFlags=DoneFlags))
    exec(compile(ast.Module(body=[n for n in util.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'rl','exec'),scope)
    node=ast.Module(body=[ast.ClassDef(name='Agent',bases=[],keywords=[],
        body=methods(z.read('MimicKit/mimickit/learning/ppo_agent.py').decode(),['_build_train_data','_compute_critic_loss']),decorator_list=[])],type_ignores=[])
scope.update(rl_util=types.SimpleNamespace(compute_td_lambda_return=scope['compute_td_lambda_return']),
    torch_util=types.SimpleNamespace(eval_minibatch=lambda fn,args,size:fn(**args)),
    mp_util=types.SimpleNamespace(calc_mean_std=lambda t:(t.mean(),t.std())))
exec(compile(ast.fix_missing_locations(node),'ppo','exec'),scope)
v=torch.nn.Parameter(torch.tensor(-30.))
data=dict(obs=torch.zeros(2,6,1),next_obs=torch.zeros(2,6,1),reward=torch.stack([e._reward_buf,torch.full((6,),.8)]),
    done=torch.stack([e._done_buf,torch.zeros(6,dtype=torch.long)]),rand_action_mask=torch.ones(2,6))
a=scope['Agent']()
vars(a).update(eval=lambda:None,_obs_norm=types.SimpleNamespace(normalize=lambda x:x),
    _model=types.SimpleNamespace(eval_critic=lambda obs:v.expand(*obs.shape[:-1],1).clone()),_critic_eval_batch_size=32,
    _discount=.99,_td_lambda=.95,_norm_adv_clip=4.,_compute_succ_val=lambda:0.,_compute_fail_val=lambda:0.,
    _exp_buffer=types.SimpleNamespace(get_data=lambda k:data[k],set_data=lambda k,x:data.__setitem__(k,x)))
a._build_train_data();target=data['tar_val']
torch.testing.assert_close(target[0,:4],torch.tensor([99.8,-28.9,-99.2,.8]))
loss=a._compute_critic_loss(dict(obs=torch.zeros(1,1),tar_val=target[0,0:1]))['critic_loss'];loss.backward()
assert v.grad<0
class Stream(io.BytesIO):
    def __init__(self,fail):super().__init__(b'checkpoint');self.fail=fail
    def read(self,n=-1):
        if self.fail:raise ReadTimeoutError(endpoint_url='test')
        return super().read(n)
class Client:
    def __init__(self,failures):self.failures=failures;self.streams=[]
    def get_object(self,**kw):
        s=Stream(len(self.streams)<self.failures);self.streams.append(s);return {'Body':s}
import backup,hashlib
backup.time.sleep=lambda _:None
c=Client(1);sha=hashlib.sha256(b'checkpoint').hexdigest();verified_readback(c,'b','k',sha)
assert len(c.streams)==2 and all(s.closed for s in c.streams)
c=Client(3)
try:verified_readback(c,'b','k',sha)
except ReadTimeoutError:pass
else:raise AssertionError('Permanent failure accepted')
assert len(c.streams)==3 and all(s.closed for s in c.streams)
result=dict(passed=True,success_target=float(target[0,0]),timeout_target=float(target[0,1]),
    failure_target=float(target[0,2]),normal_completion_target=float(target[0,3]),critic_gradient=float(v.grad),
    backup_transient_retry=True,backup_permanent_failure_propagates=True)
Path('Saved/MimicKitEquipment/success-value-tests.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
