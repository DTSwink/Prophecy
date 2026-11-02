"""Check row-specific strength, disabled motors and observation semantics."""
import preflight_slow_policy as p
import os,json,sys,torch,numpy as np
os.chdir(p.p/'MimicKit');torch.set_num_threads(2);torch.set_num_interop_threads(1);p.wp.init();p.wp.set_device('cuda:0');p.mp_util.init(0,1,'cuda:0',6760)
cfg,ec=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine']]
env=p.SlowLocoEnv(cfg,ec,64,'cuda:0',False);mask=p.wp.to_torch(env._engine.transfer_contact.p.motor_enabled);base=p.wp.to_torch(env._engine._uefn_motors.upper);expected=torch.ones_like(mask)
for motion,active,disabled in [(4,'right','left'),(5,'left','right')]:
 rows=(env._fixed_motion_ids==motion).nonzero().flatten();expected[rows[:,None],torch.tensor(env.disabled_dof_indices[disabled],device='cuda:0')[None]]=0
 for part,cap in [('thigh',env.limp_support_strength['hip_nm']),('shin',env.limp_support_strength['knee_nm']),('foot',env.limp_support_strength['ankle_nm'])]:
  joint=env._kin_char_model.get_joint(env._kin_char_model.get_body_names().index(active+'_'+part));dofs=torch.arange(joint.dof_idx,joint.dof_idx+joint.get_dof_dim(),device='cuda:0');expected[rows[:,None],dofs[None]]=cap/base[dofs][None]
torch.testing.assert_close(mask,expected);effective=base[None]*expected;peak=torch.zeros_like(mask)
for tick in range(96):
 if tick%16==0:
  obs,info=env.reset();torch.testing.assert_close(mask,expected);assert torch.equal(obs[:,154:158],env._limb_enabled)
 env.step(torch.full((64,34),12. if tick%2 else -12.,device='cuda:0'));t=env._engine._dof_forces[0].abs();assert torch.isfinite(t).all();assert bool((t<=effective+1e-3).all());peak=torch.maximum(peak,t)
print('Disabled torque numerical peak',float(peak[mask==0].max()),flush=True)
assert float(peak[mask==0].max())<1e-7  # solver roundoff, same tolerance as PPO preflight
assert float(peak[mask>1].max())>150
if len(sys.argv)>2:
 assert env.limp_support_strength['knee_nm']==float(sys.argv[2])
 for motion,side in [(4,'right'),(5,'left')]:
  rows=env._fixed_motion_ids==motion;knee=env.disabled_dof_indices[side][3]
  assert float(peak[rows,knee].max())>=float(sys.argv[2])-.01
if len(sys.argv)>3:
 assert env.limp_support_strength['hip_nm']==float(sys.argv[3])
 for motion,side in [(4,'right'),(5,'left')]:
  rows=env._fixed_motion_ids==motion
  for hip in env.disabled_dof_indices[side][:3]:
   print('Support hip',side,hip,'cap',float(effective[rows,hip].min()),'peak',float(peak[rows,hip].max()),flush=True)
   assert bool((effective[rows,hip]-float(sys.argv[3])).abs().max()<1e-3)
  assert float(peak[rows][:,env.disabled_dof_indices[side][:3]].max())>=float(sys.argv[3])-.01
normal=(env._fixed_motion_ids!=4)&(env._fixed_motion_ids!=5);assert bool((mask[normal]==1).all())
env._engine.validate_transfer_solver()
r=dict(passed=True,worlds=64,ticks=96,disabled_max_nm=float(peak[mask==0].max()),boosted_max_nm=float(peak[mask>1].max()),non_limp_caps_unchanged=True,limb_flags_binary=True,metadata=env.replay_loss_metadata()['limp_support_strength'])
(p.out/(sys.argv[1] if len(sys.argv)>1 else 'limp-strength-deploy-20261101')/'strength-test.json').write_text(json.dumps(r,indent=2));print(json.dumps(r),flush=True)
