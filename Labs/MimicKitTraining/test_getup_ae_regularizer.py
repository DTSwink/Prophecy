"""Verify actual reward routing, cohort isolation and three-frame reset history."""
import ast
import json
import types
from pathlib import Path
import torch
from perturbed_motion import MotionPrior, tracking_blend

def check(source):
    class Base:
        def _tracking_losses(self,*args):return torch.full((2,4),2.)
        def _update_reward(self):self._reward_buf=torch.full((2,),.25)
    nodes=[n for c in ast.parse(source).body if isinstance(c,ast.ClassDef) for n in c.body
           if isinstance(n,ast.FunctionDef) and n.name in ('_tracking_losses','_update_reward')]
    scope=dict(torch=torch,Base=Base,tracking_blend=tracking_blend,
               EnvMode=types.SimpleNamespace(TRAIN=1),q=types.SimpleNamespace(quat_to_matrix=lambda x:x))
    module=ast.Module(body=[ast.ClassDef(name='Trial',bases=[ast.Name(id='Base',ctx=ast.Load())],
        keywords=[],body=nodes,decorator_list=[])],type_ignores=[])
    exec(compile(ast.fix_missing_locations(module),'actual-production-methods','exec'),scope)
    for enabled in (False,True):
        e=scope['Trial']()
        vars(e).update(_perturb_ready=True,_refresh_reward_rotations=lambda:None,
            _perturbed_ids=torch.tensor([0]),_prior_ids=torch.tensor([0],dtype=torch.long) if enabled else torch.empty(0,dtype=torch.long),
            _prior=types.SimpleNamespace(append=lambda *a:None,cost=lambda:torch.tensor([5.])),
            _prior_raw=torch.zeros(2),_time_buf=torch.ones(2),_mse_only=False,
            _perturb_cfg=dict(ae_ticks=80,blend_ticks=60,getup_ae_regularizer=enabled),
            _perturbed_getup=torch.tensor([True,False]),_perturbed_rows=torch.tensor([True,False]),
            _idle_position_getup=True,_tracking_mix=torch.ones(2),_getup_position_weight=10.,
            reward_target_pos=torch.zeros(2,15,3),_ae_weight=.2,_mode=0,
            _additive_head_reward=False,_getup_reward_form='linear_cost',
            loss_term_names=('position_mse','rotation_mse','linear_velocity_mse','angular_velocity_mse','motion_prior'))
        pos=torch.ones(2,15,3)
        e.loss_terms=e._tracking_losses(pos,torch.ones(2,15,4),None,None,None,None)
        e._update_reward()
        torch.testing.assert_close(e.loss_terms[0],torch.tensor([10.,0,0,0,1. if enabled else 0.]))
        torch.testing.assert_close(e.loss_terms[1],torch.tensor([2.,2.,2.,2.,0.]))
        torch.testing.assert_close(e._reward_buf,torch.tensor([-10. if enabled else -9.,.25]))
    return True

if __name__=='__main__':
    check(Path('Labs/MimicKitTraining/perturbed_omni.py').read_text())
    check(Path('Saved/MimicKitEquipment/getup-ae-patched.py').read_text())
    p=MotionPrior('Saved/MotionRegularizer-2x512',2,'cpu')
    pos=torch.ones(2,15,3);rot=torch.eye(3).expand(2,15,3,3).clone()
    p.reset(torch.tensor([0,1]),pos,rot);assert p.cost().count_nonzero()==0
    p.append(pos,rot);assert p.cost().count_nonzero()==0
    p.append(pos,rot);before=p.cost();assert (before>0).all()
    p.reset(torch.tensor([0]),pos[:1],rot[:1]);after=p.cost()
    assert after[0]==0 and after[1]==before[1]
    assert all(not x.requires_grad for x in p.scorer.parameters())
    print(json.dumps(dict(passed=True,normal_unchanged=True,ae_reaches_reward=True,history_reset_isolated=True,default_behavior_unchanged=True)))
