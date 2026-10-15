"""Real-engine checks for fixed cohorts, reset history and stock AMP wiring."""
import os,sys,json
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
root=Path('/workspace/mimickit_trial');sys.path.insert(0,str(root/'MimicKit/mimickit'))
import torch,yaml,numpy as np
from amp_standing import StandingAMPEnv,register_network
from envs.base_env import DoneFlags
os.chdir(root/'MimicKit');torch.set_num_threads(1)
cfg=yaml.safe_load(Path('data/envs/amp_humanoid_env.yaml').read_text())
target=json.loads((root/'pipeline/amp_standing_target.json').read_text())
cfg.update(episode_length=2.,num_disc_obs_steps=3,init_pose=target['pose'],
    motion_file=str(root/'pipeline/amp_standing_target.pkl'),reset_seed=20261014,
    reset_joint_noise_degrees=5.,reset_floor_clearance_m=.002)
engine=yaml.safe_load(Path('data/engines/newton_engine.yaml').read_text())
e=StandingAMPEnv(cfg,engine,512,'cuda:0',False);obs,_=e.reset();c=e._get_char_id()
assert torch.isfinite(obs).all()
fixed=e._upright_cohort.clone();assert fixed.sum()==102 and not fixed[0]
for _ in range(3):
    ids=torch.randperm(512,device='cuda:0')[:200];e.reset(ids)
    assert torch.equal(fixed,e._upright_cohort)
    torch.testing.assert_close(e._engine.get_dof_pos(c)[fixed],e._ref_dof_pos[fixed])
    torch.testing.assert_close(e._engine.get_root_pos(c)[fixed],e._ref_root_pos[fixed])
    hist=e._disc_hist_root_pos.get_all()
    torch.testing.assert_close(hist[:,0],hist[:,-1])
    torch.testing.assert_close(hist[:,-1],e._engine.get_root_pos(c))
    floor=~fixed
    torch.testing.assert_close(e._lowest_geometry(e._engine.get_body_pos(c),e._engine.get_body_rot(c))[floor],torch.full((410,),.002,device='cuda:0'),atol=2e-6,rtol=0)
assert e._num_disc_obs_steps==3
demo=e._fetch_disc_demo_data(torch.zeros(8,dtype=torch.long,device='cuda:0'),torch.rand(8,device='cuda:0'))
for v in demo:torch.testing.assert_close(v[:,0],v[:,-1])
assert demo[2].abs().max()==0 and demo[3].abs().max()==0 and demo[5].abs().max()==0
# Deliberately inject exactly the vanilla torso-contact failure signal.
getforces=e._engine.get_ground_contact_forces
forces=torch.zeros_like(getforces(c));forces[:,1,2]=1
e._engine.get_ground_contact_forces=lambda _:forces
e._time_buf[:]=.5;e._update_done()
assert (e._done_buf[fixed]==DoneFlags.FAIL.value).all()
assert (e._done_buf[~fixed]==DoneFlags.NULL.value).all()
e._time_buf[:]=2.;e._update_done()
assert (e._done_buf[~fixed]==DoneFlags.TIME.value).all()
e._engine.get_ground_contact_forces=getforces
e.reset();pose=e._init_dof_pos.expand(512,-1)
start_head=e._engine.get_body_pos(c)[fixed,2,2].mean().item()
for i in range(60):
    obs,reward,done,info=e.step(pose)
    assert torch.isfinite(obs).all()
    if i<59:assert (done[~fixed]==0).all()
assert (done[~fixed]==DoneFlags.TIME.value).all()
end_head=e._engine.get_body_pos(c)[fixed,2,2].mean().item()
assert end_head>1.1 and (done[fixed]!=DoneFlags.FAIL.value).all(), 'Reference stance falls under the stock hold controller'
register_network()
from learning.nets import net_builder
net,_=net_builder.build_net('fc_1024_1024',{'obs':e.get_obs_space()})
assert [m.out_features for m in net if isinstance(m,torch.nn.Linear)]==[1024,1024]
report=dict(passed=True,upright_worlds=102,floor_worlds=410,fixed_cohorts_after_partial_resets=True,
    upright_only_early_termination=True,static_reference_velocity_zero=True,actual_reset_history=True,
    held_target_start_head_m=start_head,held_target_end_head_m=end_head,
    held_target_upright_failures=int((done[fixed]==1).sum()),
    observations=list(obs.shape),disc_observations=list(info['disc_obs'].shape))
(root/'amp-standing-smoke.json').write_text(json.dumps(report,indent=2))
print('AMP_STANDING_PASS',json.dumps(report),flush=True)
