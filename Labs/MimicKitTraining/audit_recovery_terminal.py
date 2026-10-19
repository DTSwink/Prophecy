"""Read-only CPU reproduction of terminal-value handling in production PPO."""
import ast,json
from pathlib import Path
from types import SimpleNamespace as NS
import torch

ROOT=Path(__file__).resolve().parents[2]
vendor=ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit'
torch.set_num_threads(1)
def function(path,name):
    tree=ast.parse(path.read_text(encoding='utf-8'))
    return next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
base_tree=ast.parse((vendor/'envs/base_env.py').read_text())
flags=next(n for n in base_tree.body if isinstance(n,ast.ClassDef) and n.name=='DoneFlags')
import enum
scope={'enum':enum,'torch':torch}
exec(compile(ast.Module(body=[flags],type_ignores=[]),'production flags','exec'),scope)
DoneFlags=scope['DoneFlags'];scope['base_env']=NS(DoneFlags=DoneFlags)
exec(compile(ast.Module(body=[function(vendor/'learning/rl_util.py','compute_td_lambda_return')],type_ignores=[]),'production return','exec'),scope)
scope['rl_util']=NS(compute_td_lambda_return=scope['compute_td_lambda_return'])
scope['torch_util']=NS(eval_minibatch=lambda fn,inputs,batch:fn(**inputs))
scope['mp_util']=NS(calc_mean_std=lambda value:(value.mean(),value.std()))
exec(compile(ast.Module(body=[function(vendor/'learning/ppo_agent.py','_build_train_data')],type_ignores=[]),'production PPO','exec'),scope)
data={'obs':torch.zeros(1,3,1),'next_obs':torch.full((1,3,1),10.),
      'reward':torch.full((1,3),.2),'done':torch.tensor([[DoneFlags.TIME.value,DoneFlags.SUCC.value,DoneFlags.FAIL.value]]),
      'rand_action_mask':torch.ones(1,3)}
agent=NS(eval=lambda:None,_exp_buffer=NS(get_data=data.__getitem__,set_data=data.__setitem__),
         _obs_norm=NS(normalize=lambda x:x),_model=NS(eval_critic=lambda obs:obs),
         _critic_eval_batch_size=0,_compute_succ_val=lambda:0.,_compute_fail_val=lambda:0.,
         _discount=.99,_td_lambda=.95,_norm_adv_clip=4.)
scope['_build_train_data'](agent)
torch.testing.assert_close(data['tar_val'],torch.tensor([[10.1,.2,.2]]))
# Corrected recovery completion must emit SUCC and zero continuation value.
class Base:
    def _update_done(self):self._done_buf.zero_()
method=function(Path(__file__).with_name('recovery_omni.py'),'_update_done')
cls=ast.ClassDef(name='Recovery',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=[method],decorator_list=[])
scope.update(Base=Base)
exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),'production completion','exec'),scope)
env=scope['Recovery']();env._recovery_ready=True;env._recovery_ids=torch.tensor([0]);env._get_char_id=lambda:0
env._recovery_timeout_only=False;env._recovery_sphere_only=True;env._time_buf=torch.tensor([1.4])
env._episode_length=10.;env._reset_after_getup=True;env.recovery_active=lambda:torch.tensor([False])
env._done_buf=torch.zeros(1,dtype=torch.long);env.target_distances_sq=torch.zeros(1,5)
env._recovery_target_indices=list(range(5));env._recovery_target_radius_sq=torch.full((5,),.3**2)
env._update_done();assert env._done_buf.item()==DoneFlags.SUCC.value
result=dict(passed=True,completed_recovery_flag=env._done_buf.item(),
    synthetic_reward=.2,synthetic_next_value=10.,actual_timeout_target=float(data['tar_val'][0,0]),
    finite_episode_terminal_target=float(data['tar_val'][0,1]),
    note='Regression passes: authored clip completion uses SUCC; ordinary timeout retains bootstrapping.')
out=ROOT/'Saved/MimicKitEquipment/getup-loop-audit/terminal-fixed-test.json'
out.write_text(json.dumps(result,indent=2));print(json.dumps(result))
