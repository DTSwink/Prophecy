"""Verify passive-only MSE removal against the prior objective and real steps."""
import os,json
import preflight_slow_policy as p
import torch
from omni_walk import OmniWalkEnv
from util import torch_util as q
os.chdir(p.p/'MimicKit');torch.set_num_threads(2);torch.set_num_interop_threads(1)
p.wp.init();p.wp.set_device('cuda:0');p.mp_util.init(0,1,'cuda:0',6768)
cfg,ec=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine']]
env=p.SlowLocoEnv(cfg,ec,64,'cuda:0',False);env.reset();enabled=env._mse_body_enabled
ids=env._fixed_motion_ids;normal=(ids!=4)&(ids!=5);assert enabled[normal].all()
assert torch.equal((~enabled).sum((1,2)),torch.where(normal,0,3))
tp=env.reward_target_pos;tr=env.reward_target_rot;tv=torch.randn_like(tp);ta=torch.randn_like(tp)
pos=tp+torch.randn_like(tp)*.1;rot=q.exp_map_to_quat(torch.randn_like(tp));vel=tv+torch.randn_like(tp);ang=ta+torch.randn_like(tp)
before=OmniWalkEnv._tracking_losses(env,pos,rot,vel,ang,tv,ta)
after=env._tracking_losses(pos,rot,vel,ang,tv,ta)
torch.testing.assert_close(before[normal],after[normal],rtol=1e-6,atol=1e-6)
torch.testing.assert_close(before[:,-1],after[:,-1],rtol=0,atol=0)
# Independent per-body formula, including all four distinct reductions.
expected=torch.stack([((pos-tp).square()*enabled).mean((1,2)),((vel-tv).square()*enabled).mean((1,2)),
    ((q.quat_to_matrix(rot)-q.quat_to_matrix(tr)).square()*enabled[...,None]).mean((1,2,3)),
    ((ang-ta).square()*enabled).mean((1,2))],-1)*env._loss_weights
torch.testing.assert_close(after[:,:4],expected)
# Arbitrarily large passive-body errors must contribute exactly zero.
only=env._tracking_losses(torch.where(enabled,tp,tp+100),torch.where(enabled,tr,rot),
    torch.where(enabled,tv,tv+100),torch.where(enabled,ta,ta+100),tv,ta)
assert torch.equal(only[:,:4],torch.zeros_like(only[:,:4]))
changed=env._tracking_losses(torch.where(enabled,pos,tp),torch.where(enabled,rot,tr),
    torch.where(enabled,vel,tv),torch.where(enabled,ang,ta),tv,ta)
assert (changed[:,:4]>0).all()
motor_mask=p.wp.to_torch(env._engine.transfer_contact.p.motor_enabled)
for tick in range(12):
    env.step(torch.randn((64,34),device='cuda:0'))
    assert torch.isfinite(env.loss_terms).all()
    assert float(env._engine._dof_forces[0][motor_mask==0].abs().max())==0
    if tick==5:env.reset(torch.arange(0,64,3,device='cuda:0'))
assert torch.equal(enabled,env._mse_body_enabled)
report=dict(passed=True,normal_rows_numerically_unchanged=True,normal_max_float_error=float((before[normal]-after[normal]).abs().max()),enabled_body_weights_unchanged=True,
    passive_error_contribution_exactly_zero=True,all_four_terms_verified=True,
    flat_com_unchanged=True,disabled_motor_torque_zero=True,real_steps=12,
    metadata=env.replay_loss_metadata()['disabled_leg_mse'])
(p.out/'passive-leg-mse-deploy-20261101/mask-test.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
