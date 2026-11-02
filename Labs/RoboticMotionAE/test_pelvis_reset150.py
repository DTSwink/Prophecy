"""Rolling displacement invariants and actual slow-loco done integration."""
import preflight_slow_policy as p
import torch, json, os, time
from slow_loco_env import PeriodicPelvisTarget

def numerical():
    w=PeriodicPelvisTarget(torch.tensor([150]*4), 'cpu')
    ids=torch.arange(4);zero=torch.zeros(4,3);w.reset(ids,zero,zero)
    for tick in range(1,451):
        reference=zero.clone();reference[:,0]=tick*.025
        actual=reference.clone();actual[:,0]*=.95
        actual[1,0]=0.;actual[2,2]=-.31
        w.update(actual,reference)
        since=tick%150
        torch.testing.assert_close(w.radius,torch.full_like(w.radius,.30))
        # Constant world progress between resets; exact recenter at150/300/450.
        torch.testing.assert_close(w.target[0,0]-actual[0,0],torch.tensor(since*.025*.05),atol=2e-6,rtol=1e-5)
        torch.testing.assert_close(w.target[1,0],torch.tensor(since*.025))
        assert w.ready.all()
        assert not w.sphere_failed(actual)[0]
        assert bool(w.sphere_failed(actual)[1]) == (since*.025>.30001)
        assert w.sphere_failed(actual)[2]  # Height remains checked even on recenter.
    # Boundary is a sphere, not a box/cylinder, active immediately.
    w.reset(ids,zero,zero);w.update(zero,zero)
    probe=zero.clone();probe[:,0]=.30
    assert not w.sphere_failed(probe).any()
    probe[:,2]=.01;assert w.sphere_failed(probe).all()
    # Partial resets change neither untouched ages nor anchors.
    w.age[:]=149;before=w.age.clone();w.reset(ids[::2],zero[::2],zero[::2])
    assert (w.age[::2]==0).all() and torch.equal(w.age[1::2],before[1::2])
    w.update(zero,zero)
    assert w.age.tolist()==[1,150,1,150]
    return dict(reset_every_ticks=150,fixed_radius_m=.30,full_xyz_sphere=True,
        active_from_first_tick=True,world_motion_between_resets=True,
        recenter_at150_300_450=True,height_never_recentred=True,partial_reset_isolated=True,
        stationary_fails_before_recenter=True)

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
# Force immediate world-sphere failure with unchanged live actual pose.
env.reward_target_pos.copy_(pos);env.reward_target_rot.copy_(rot)
ref=pos[:,env._pelvis_id].clone();env._pelvis_window.reset(ids,ref,ref)
env._pelvis_window.age.zero_()
env._ref_body_pos[:,env._pelvis_id,0]=ref[:,0]+1.
env._reward_buf.fill_(.4);env._update_done()
assert (env._done_buf==1).all();torch.testing.assert_close(env._reward_buf,torch.full_like(env._reward_buf,-99.6))
# Height is always checked; timeout is not penalized.
for height in (.0,.301):
 env._ref_body_pos[:,env._pelvis_id].copy_(ref);env._pelvis_window.reset(ids,ref,ref)
 env._ref_body_pos[:,env._pelvis_id,2]+=height;env._reward_buf.fill_(.4);env._update_done()
 assert (env._done_buf==(1 if height else 0)).all()
env._ref_body_pos[:,env._pelvis_id].copy_(ref);env._pelvis_window.reset(ids,ref,ref)
env._time_buf.fill_(10);env._motion_time_offsets.fill_(-10);env._reward_buf.fill_(.4);env._update_done()
assert (env._done_buf==3).all();torch.testing.assert_close(env._reward_buf,torch.full_like(env._reward_buf,.4))
report=dict(passed=True,checks=checks,other_spheres=point_checks,live_done_and_penalty=True,immediate_height=True,timeout_free=True,metadata=env.replay_loss_metadata()['target_deviation'],checked_unix=time.time())
(p.out/'pelvis-reset150-deploy-20261101/termination-test.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
