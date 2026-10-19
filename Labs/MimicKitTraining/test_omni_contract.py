"""Local CPU contract checks. No optimizer steps, training or allocation."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),
             str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
import json
import numpy as np
import torch
from gymnasium.spaces import Box
from unittest.mock import patch
from omni_policy import OmniPPOModel, circular_phase
from omni_walk import OmniWalkEnv, phase_at, row_motion_weights, fixed_motion_rows
from absolute_walk import AbsoluteWalkEnv


def run():
    torch.set_num_threads(1)
    # Test actual environment observation assembly without physics. Sentinel
    # physical state remains unchanged; exactly five floats are appended.
    env=object.__new__(OmniWalkEnv)
    env._motion_ids=torch.tensor([0,1,2])
    env._gaits=torch.tensor([-1.,0.,1.])
    env._directions=torch.tensor([[1.,0.],[1.,0.],[0.,-1.]])
    env._phase_offsets=torch.tensor([0.,.25,.6])
    times=torch.tensor([9.99,.1,.599999]);duration=torch.tensor([10.,1.,.6])
    class Lib:
        def get_motion_length(self,ids):return duration[ids]
    class Engine:
        def get_timestep(self):return 1/30
    env._motion_lib=Lib();env._engine=Engine()
    env._get_motion_times=lambda ids=None:times if ids is None else times[ids]
    physical=torch.arange(3*142,dtype=torch.float32).view(3,142)
    with patch.object(AbsoluteWalkEnv,'_compute_obs',lambda self,ids=None:physical if ids is None else physical[ids]):
        obs=env._compute_obs();subset=env._compute_obs(torch.tensor([2,0]))
    assert obs.shape==(3,147)
    torch.testing.assert_close(obs[:,:142],physical)
    torch.testing.assert_close(subset,obs[[2,0]])
    env._equipment_conditioning=True
    env._equipment=torch.tensor([0.,1.,0.]);env._arm_enabled=torch.ones(3,2)
    with patch.object(AbsoluteWalkEnv,'_compute_obs',lambda self,ids=None:physical if ids is None else physical[ids]):
        equipment=env._compute_obs();part=env._compute_obs(torch.tensor([2,0]))
    assert equipment.shape==(3,150)
    torch.testing.assert_close(equipment[:,:145],obs[:,:145])
    torch.testing.assert_close(equipment[:,145:148],torch.tensor([[0.,1.,1.],[1.,1.,1.],[0.,1.,1.]]))
    torch.testing.assert_close(equipment[:,-2:],obs[:,-2:]);torch.testing.assert_close(part,equipment[[2,0]])
    count,pools=row_motion_weights(torch.tensor([-1.,0.,1.,-1.,0.,1.]),torch.ones(6),.06,512)
    assert count==31
    torch.testing.assert_close(pools[1],torch.tensor([.5,0,0,.5,0,0]))
    assert pools[0,[0,3]].sum()==0
    # Fixed assignments preserve weighted quotas and cannot migrate to easier
    # motions when arbitrary subsets of agents repeatedly fail.
    assigned=fixed_motion_rows(pools,count,512)
    torch.testing.assert_close(assigned,fixed_motion_rows(pools,count,512))
    for ids in (torch.arange(512),torch.tensor([511,0,31,30,9,74])):
        chosen=assigned[ids]
        torch.testing.assert_close((chosen==0)|(chosen==3),ids<count)
    for pool,n,rows in ((pools[1],count,assigned[:count]),(pools[0],512-count,assigned[count:])):
        assert ((torch.bincount(rows,minlength=6)-pool*n).abs()<=1).all()
    # Exercise the real reset method, including phase randomization and target
    # state updates. More resets must not imply more motion resampling.
    reset=object.__new__(OmniWalkEnv)
    reset._device='cpu';reset._idle_rows=count;reset._fixed_motion_ids=assigned
    reset._motion_ids=torch.full((512,),-1,dtype=torch.long)
    reset._motion_time_offsets=torch.zeros(512);reset._rand_reset=True
    for name in ('root_pos','root_rot','root_vel','root_ang_vel','joint_rot','dof_vel','body_pos','body_rot','dof_pos'):
        setattr(reset,'_ref_'+name,torch.zeros(512,1))
    class ResetLib:
        def sample_time(self,ids):return torch.rand(len(ids))
        def calc_motion_frame(self,ids,times):return tuple(ids[:,None].float()+times[:,None] for _ in range(6))
        def joint_rot_to_dof(self,values):return values
    class Kinematics:
        def forward_kinematics(self,p,r,j):return p,r
    reset._motion_lib=ResetLib();reset._kin_char_model=Kinematics()
    reset._reset_ref_motion(torch.arange(512));old_times=reset._motion_time_offsets.clone()
    ids=torch.tensor([511,0,31,30,9,74])
    for _ in range(20):reset._reset_ref_motion(ids)
    torch.testing.assert_close(reset._motion_ids,assigned)
    assert (reset._motion_time_offsets[ids]!=old_times[ids]).all()
    untouched=torch.ones(512,dtype=torch.bool);untouched[ids]=False
    torch.testing.assert_close(reset._motion_time_offsets[untouched],old_times[untouched])
    reset._rand_reset=False;reset._reset_ref_motion(ids)
    assert (reset._motion_time_offsets[ids]==0).all()
    torch.testing.assert_close(obs[:,142],torch.tensor([-1.,0.,1.]))
    torch.testing.assert_close(obs[:,143:145],torch.tensor([[1.,0.],[1.,0.],[0.,-1.]]))
    before=times.clone();target=env.next_phase_target()
    torch.testing.assert_close(times,before) # no clock feedback
    torch.testing.assert_close(target,circular_phase((times+1/30)/duration[env._motion_ids]+env._phase_offsets[env._motion_ids]),atol=1e-6,rtol=1e-5)
    torch.testing.assert_close(phase_at(torch.tensor([1.-1e-7]),torch.ones(1),torch.zeros(1)),
                               phase_at(torch.tensor([1.+1e-7]),torch.ones(1),torch.zeros(1)),atol=2e-6,rtol=0)
    class Spaces:
        def get_obs_space(self):return Box(-np.inf,np.inf,(147,))
        def get_action_space(self):return Box(-1.,1.,(34,))
    config=dict(actor_net='fc_1024_512_512',critic_net='fc_1024_512_512',
                actor_init_output_scale=.01,actor_std_type='FIXED',action_std=.05)
    model=OmniPPOModel(config,Spaces())
    for trunk in (model._actor_layers,model._critic_layers):
        assert [m.out_features for m in trunk if isinstance(m,torch.nn.Linear)]==[1024,512,512]
    x=torch.randn(3,147);pred=model.eval_phase(x)
    assert pred.shape==(3,2) and model.eval_critic(x).shape==(3,1)
    action=model.eval_actor(x).sample();assert action.shape==(3,34)
    actor_ids={id(p) for p in model.get_actor_params()}
    assert all(id(p) in actor_ids for p in model._phase_out.parameters())
    ((pred-target)**2).mean().backward()
    assert model._phase_out.weight.grad.abs().sum()>0
    assert model._actor_layers[0].weight.grad.abs().sum()>0
    assert all(p.grad is None for p in model._action_dist.parameters())
    assert all(p.grad is None for p in model._critic_layers.parameters())
    unit=OmniPPOModel(dict(config,auto_phase_unit_output=True),Spaces())
    pred=unit.eval_phase(x);torch.testing.assert_close(pred.norm(dim=-1),torch.ones(3))
    torch.testing.assert_close((pred+pred).square().mean(-1),torch.full((3,),2.))
    loss=(pred-target).square().mean();loss.backward()
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in unit.parameters())
    report=dict(passed=True,device='cpu',hidden_widths=[1024,512,512],command_floats=5,
                motor_outputs=34,phase_outputs=2,wrap_test=True,subset_test=True,idle_mode=-1,idle_direction=[1,0],
                phase_backprop=True,optimizer_steps=0,physics_test=False,
                note='142 physical inputs here are a test fixture, not a measured integrated observation count')
    (ROOT/'Saved/MimicKitUEFN/omni-contract-tests.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':run()
