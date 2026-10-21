"""CPU checks for the reward boundary, reward composition and replay quotas."""
import ast
from pathlib import Path
from types import SimpleNamespace
import torch
from perturbed_motion import getup_head_height_reward

h=torch.tensor([.7,.7,.7,-.2,2.,.7])
t=torch.full_like(h,1.4)
ticks=torch.tensor([59,60,61,61,61,61])
mask=torch.tensor([True,True,True,True,True,False])
torch.testing.assert_close(getup_head_height_reward(h,t,ticks,mask),torch.tensor([0.,0.,.5,0.,1.,0.]))

# Execute the actual environment override against a small parent reward stub.
tree=ast.parse(Path(__file__).with_name('perturbed_omni.py').read_text())
method=next(n for n in tree.body if isinstance(n,ast.ClassDef)).body
method=next(n for n in method if isinstance(n,ast.FunctionDef) and n.name=='_update_reward')
class Parent:
    def _update_reward(self): self._reward_buf=torch.reciprocal(1+self.loss_terms.sum(-1))
cls=ast.ClassDef(name='TestEnv',bases=[ast.Name(id='Parent',ctx=ast.Load())],keywords=[],body=[method],decorator_list=[])
scope=dict(Parent=Parent,torch=torch,getup_head_height_reward=getup_head_height_reward,EnvMode=SimpleNamespace(TRAIN=1))
exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),'reward_override','exec'),scope)
env=scope['TestEnv']();env._perturb_ready=True;env._additive_head_reward=True
env._engine=SimpleNamespace(get_body_pos=lambda _:h[:,None,None].expand(-1,1,3))
env._get_char_id=lambda:0;env._head_id=0;env._idle_head_height=t;env._motion_ids=torch.arange(6)
env._time_buf=ticks/30.;env._perturbed_getup=mask;env._head_height_reward=torch.zeros(6)
env.loss_terms=torch.ones((6,1))*3;env._mode=1;env._reward_diagnostics=torch.zeros(4);env.get_num_envs=lambda:6
env._update_reward()
torch.testing.assert_close(env._reward_buf,torch.tensor([.25,.25,.75,.25,1.25,.25]))
assert torch.equal(env.loss_terms,torch.full((6,1),3.))
assert env._reward_diagnostics[0]==1.5

tree=ast.parse(Path(__file__).with_name('observe_many.py').read_text())
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='limit_idle_replays')
scope={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'replay_selection','exec'),scope)
for round_id in range(8):
    before=list(range(20));motions=list(range(30));recovery=[False]*4+[True]*4+[False]*22
    perturbed=[i%2==0 for i in range(30)]
    after=scope['limit_idle_replays'](before,motions,8,recovery,perturbed,round_id)
    assert len(after)==len(set(after))==20
    assert sum(w<8 and not recovery[w] for w in after)==2
    assert set(range(4,20)).issubset(after)
    assert all(w>=8 and perturbed[w] for w in set(after)-set(before))
print('PASS: tick61 activation, clipping, cohort mask, actual additive reward override, no loss mixing, two idle rows and perturbed replacements')
