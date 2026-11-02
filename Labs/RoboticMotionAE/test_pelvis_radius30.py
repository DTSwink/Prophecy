"""Rolling displacement invariants and actual slow-loco done integration."""
import preflight_slow_policy as p
import torch, json, os, time
from slow_loco_env import RollingPelvisTarget

def numerical():
    w=RollingPelvisTarget(torch.tensor([70]*6), 'cpu')
    ids=torch.arange(6);zero=torch.zeros(6,3);w.reset(ids,zero,zero)
    ratios=torch.tensor([1.,.95,.90,.70,0.,1.])
    fails=[]
    for tick in range(1,401):
        reference=zero.clone();reference[:,0]=tick/30*.75
        actual=reference*ratios[:,None]
        actual[5,1]=tick/30*.75  # wrong direction / sideways drift
        w.update(actual,reference)
        fail=w.sphere_failed(actual)&w.ready
        if tick<70:assert not fail.any()
        else:assert fail.tolist()==[False,False,False,True,True,True],(tick,fail)
    # A true 3D sphere, not independent XY/height bounds; test its boundary.
    expected_radius=.30+.10*70*.025
    torch.testing.assert_close(w.radius,torch.full_like(w.radius,expected_radius))
    probe=w.target.clone();probe[:,0]+=expected_radius
    assert not w.sphere_failed(probe).any()
    probe[:,2]+=.01
    assert w.sphere_failed(probe).all()
    # A static reference still retains the full 30cm spatial allowance.
    w.reset(ids,zero,zero);w.update(zero,zero)
    for offset,expected in [(.299,False),(.301,True)]:
        probe=zero.clone();probe[:,0]=offset
        assert w.sphere_failed(probe).tolist()==[expected]*6
    # Large old position offset expires; current correct velocity is enough.
    w.reset(ids,zero,zero)
    for tick in range(1,201):
        reference=zero.clone();reference[:,0]=tick*.025
        actual=reference.clone();actual[:,0]-=2.
        w.update(actual,reference)
        if tick>70:torch.testing.assert_close(actual[:,:2],w.target[:,:2])
    # Partial reset restarts only those histories; no cross-episode contamination.
    before=w.age.clone();w.reset(ids[::2],actual[::2],reference[::2])
    assert (w.age[::2]==0).all() and torch.equal(w.age[1::2],before[1::2])
    w.update(actual+.025,reference+.025)
    torch.testing.assert_close(w.target[::2,:2],(actual+.025)[::2,:2])
    assert not w.ready[::2].any() and w.ready[1::2].all()
    return dict(two_cycles=70,perfect_passes=True,ninety_five_percent_passes=True,ninety_percent_passes=True,base_30cm_preserved=True,three_dimensional_sphere=True,seventy_percent_fails=True,stationary_fails=True,sideways_fails=True,old_drift_expires=True,partial_reset_isolated=True)

os.chdir(p.p/'MimicKit');torch.set_num_threads(2)
checks=numerical()
p.wp.init();p.wp.set_device('cuda:0');p.mp_util.init(0,1,'cuda:0',6752)
cfg,ec=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine')]
cfg.pop('slow_loco_motion_subset',None)
env=p.SlowLocoEnv(cfg,ec,64,'cuda:0',False);env.reset()
char=env._get_char_id();pos=env._engine.get_body_pos(char).clone();rot=env._engine.get_body_rot(char).clone();ids=torch.arange(64,device='cuda:0')
point_checks=[]
for point in env._termination_points[:-1]:
    idx=env._kin_char_model.get_body_names().index(point['body'])
    for distance in (.26,.28,.53,.55):
        env.reward_target_pos.copy_(pos);env.reward_target_rot.copy_(rot)
        env._ref_body_pos[:,env._pelvis_id].copy_(pos[:,env._pelvis_id])
        env._pelvis_window.reset(ids,pos[:,env._pelvis_id],pos[:,env._pelvis_id])
        env.reward_target_pos[:,idx,0]+=distance;env._time_buf.fill_(1/30);env._reward_buf.fill_(.4)
        env._update_done()
        threshold=torch.where((env._motion_ids==4)|(env._motion_ids==5),.54,.27)
        expected=distance>threshold
        if point['body']=='left_foot':expected &= env._motion_ids!=4
        if point['body']=='right_foot':expected &= env._motion_ids!=5
        torch.testing.assert_close(env._done_buf==1,expected)
        torch.testing.assert_close(env._reward_buf,.4-100*expected.float())
        point_checks.append(dict(body=point['body'],distance=distance,failures=int(expected.sum())))
# Force a full-window horizontal failure with unchanged live actual pose.
env.reward_target_pos.copy_(pos);env.reward_target_rot.copy_(rot)
ref=pos[:,env._pelvis_id].clone();env._pelvis_window.reset(ids,ref,ref)
env._pelvis_window.age.copy_(env._pelvis_window.windows-1)
env._ref_body_pos[:,env._pelvis_id,0]=ref[:,0]+1.
env._reward_buf.fill_(.4);env._update_done()
assert (env._done_buf==1).all();torch.testing.assert_close(env._reward_buf,torch.full_like(env._reward_buf,-99.6))
# Height still immediate during warmup; then timeout is not penalized.
for height in (.0,.301):
 env._ref_body_pos[:,env._pelvis_id].copy_(ref);env._pelvis_window.reset(ids,ref,ref)
 env._ref_body_pos[:,env._pelvis_id,2]+=height;env._reward_buf.fill_(.4);env._update_done()
 assert (env._done_buf==(1 if height else 0)).all()
env._ref_body_pos[:,env._pelvis_id].copy_(ref);env._pelvis_window.reset(ids,ref,ref)
env._time_buf.fill_(10);env._motion_time_offsets.fill_(-10);env._reward_buf.fill_(.4);env._update_done()
assert (env._done_buf==3).all();torch.testing.assert_close(env._reward_buf,torch.full_like(env._reward_buf,.4))
report=dict(passed=True,checks=checks,other_spheres=point_checks,live_done_and_penalty=True,immediate_height=True,timeout_free=True,metadata=env.replay_loss_metadata()['target_deviation'],checked_unix=time.time())
(p.out/'pelvis-radius30-deploy-20261101/termination-test.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
