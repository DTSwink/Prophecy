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
r=Path('/workspace/mimickit_trial');up=r/'MimicKit/mimickit'
ns=dict(torch=torch,DoneFlags=DoneFlags,Base=Base,com2_velocity=lambda *a:torch.zeros(6,2),com2_failure=lambda *a:torch.zeros(6,dtype=torch.bool))
x=klass('Trial',[method('/tmp/penalty_perturbed_omni.py','_update_done')],ns)()
p=torch.zeros(6,1,3);p[:,0,2]=torch.tensor([.4,.4,.5,.501,.4,.91])
vars(x).update(_perturb_ready=True,_time_buf=torch.tensor([59,60,60,60,60,60])/30,_perturbed_getup=torch.tensor([1,1,1,1,0,1],dtype=torch.bool),_perturbed_rows=torch.tensor([1,1,1,1,0,1],dtype=torch.bool),_episode_length=6,_perturb_cfg=dict(getup_ticks=180,grace_ticks=8,min_speed_ratio=.7,getup_low_head_failure_fraction=.5,getup_low_head_failure_tick=60,getup_failure_penalty=100.),_head_id=0,_head_reset_height=torch.tensor([.9]),_idle_head_height=torch.tensor([1.]),_motion_ids=torch.zeros(6,dtype=torch.long),_gaits=torch.tensor([-1]),_com2_ids=[0],_com2_masses=torch.ones(1),_com2_targets=torch.zeros(1,2),_done_buf=torch.zeros(6,dtype=torch.long),_reset_reason=torch.zeros(6,dtype=torch.long),_reward_buf=torch.ones(6),_get_char_id=lambda:0,_engine=types.SimpleNamespace(get_body_pos=lambda *a:p,get_body_vel=lambda *a:torch.zeros(6,1,3)))
x._update_done();assert x._done_buf.tolist()==[0,1,1,0,0,3];assert x._reward_buf.tolist()==[1,-99,-99,1,1,1]
# Use the deployed TD-lambda and PPO code, with small in-memory buffer/model.
utilns=dict(torch=torch,base_env=types.SimpleNamespace(DoneFlags=DoneFlags))
tree=ast.parse((up/'learning/rl_util.py').read_text());tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef)];exec(compile(tree,'rl_util','exec'),utilns)
ns.update(base_env=types.SimpleNamespace(DoneFlags=DoneFlags),rl_util=types.SimpleNamespace(compute_td_lambda_return=utilns['compute_td_lambda_return']),torch_util=types.SimpleNamespace(eval_minibatch=lambda fn,args,size:fn(**args)),mp_util=types.SimpleNamespace(calc_mean_std=lambda t:(t.mean(),t.std())))
A=klass('Agent',[method(up/'learning/ppo_agent.py',n) for n in ['_build_train_data','_compute_critic_loss']],ns)
class Buffer:
    def __init__(self,reward): self.d=dict(obs=torch.zeros(3,2,1),next_obs=torch.zeros(3,2,1),reward=reward,done=torch.tensor([[0,0],[1,3],[0,0]]),rand_action_mask=torch.ones(3,2))
    def get_data(self,k):return self.d[k]
    def set_data(self,k,v):self.d[k]=v
v=torch.nn.Parameter(torch.tensor(2.));a=A();a.eval=lambda:None;a._obs_norm=types.SimpleNamespace(normalize=lambda x:x);a._model=types.SimpleNamespace(eval_critic=lambda obs:v.expand(*obs.shape[:-1],1));a._critic_eval_batch_size=16;a._discount=.99;a._td_lambda=.95;a._norm_adv_clip=4.;a._compute_succ_val=lambda:0.;a._compute_fail_val=lambda:0.
r0=torch.ones(3,2);a._exp_buffer=Buffer(r0);a._build_train_data();before=a._exp_buffer.d['tar_val'].clone()
r1=r0.clone();r1[1,0]-=100;a._exp_buffer=Buffer(r1);a._build_train_data();after=a._exp_buffer.d['tar_val'];delta=after-before
assert abs(delta[1,0].item()+100)<1e-5
assert abs(delta[0,0].item()+94.05)<1e-4
assert delta[:,1].abs().max()==0 and delta[2,0]==0
loss=a._compute_critic_loss(dict(obs=torch.zeros(1,1),tar_val=after[1,0].reshape(1)))['critic_loss'];loss.backward();assert v.grad>0
print(json.dumps(dict(env_rewards=x._reward_buf.tolist(),critic_target_terminal=float(after[1,0]),critic_target_penalty_delta=float(delta[1,0]),previous_tick_delta=float(delta[0,0]),critic_gradient=float(v.grad),reset_column_unchanged=True,following_episode_unchanged=True)))
