"""Exercise the real slow-loco done path on all motions and target points."""
import preflight_slow_policy as p
import torch, json, os, time

os.chdir(p.p/'MimicKit')
torch.set_num_threads(2)
p.wp.init(); p.wp.set_device('cuda:0'); p.mp_util.init(0,1,'cuda:0',6752)
cfg,ec=[p.yaml.safe_load((p.out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine')]
env=p.SlowLocoEnv(cfg,ec,64,'cuda:0',False)
env.reset()
env._time_buf.fill_(1/30); env._motion_time_offsets.zero_()
char=env._get_char_id()
pos=env._engine.get_body_pos(char).clone(); rot=env._engine.get_body_rot(char).clone()
checks=[]
for point in env._termination_points:
    body=point['body']; idx=env._kin_char_model.get_body_names().index(body)
    for distance in (.26,.28,.53,.55,5.):
        env.reward_target_pos.copy_(pos); env.reward_target_rot.copy_(rot)
        env.reward_target_pos[:,idx,0] += distance
        env._update_done()
        threshold=torch.full((64,),.27,device='cuda:0')
        if body.endswith('_foot'):threshold[(env._motion_ids==4)|(env._motion_ids==5)]=.54
        expected=distance>threshold
        if body=='left_foot':expected &= env._motion_ids!=4
        if body=='right_foot':expected &= env._motion_ids!=5
        torch.testing.assert_close(env._done_buf==1,expected)
        checks.append(dict(body=body,distance=distance,failures=int(expected.sum())))
# Exempt foot cannot erase a failure from a different point.
env.reward_target_pos.copy_(pos); env.reward_target_rot.copy_(rot)
for body in ('head','left_foot','right_foot'):
    env.reward_target_pos[:,env._kin_char_model.get_body_names().index(body),0] += .28
env._update_done(); assert (env._done_buf==1).all()
# Motion wrap must not reset; ordinary episode timeout remains.
env.reward_target_pos.copy_(pos)
env._motion_time_offsets.fill_(100)
env._update_done(); assert (env._done_buf==0).all()
lib=env._motion_lib
ids=torch.arange(8,device='cuda:0');length=lib.get_motion_length(ids)
assert (lib.get_motion_loop_mode(ids)==1).all()
first=lib.calc_motion_frame(ids,length*.23)
second=lib.calc_motion_frame(ids,length*1.23)
torch.testing.assert_close(second[0]-first[0],lib._motion_wrap_delta,atol=2e-5,rtol=2e-5)
for x,y in zip(first[1:],second[1:]):torch.testing.assert_close(x,y,atol=2e-4,rtol=2e-4)
env._motion_time_offsets.zero_(); env._time_buf.fill_(10)
env._motion_time_offsets.fill_(-10)
env._update_done(); assert (env._done_buf==3).all()
report=dict(passed=True,checks=checks,other_failure_preserved=True,clip_wrap_without_reset=True,reference_cycle_parity=True,timeout_preserved=True,metadata=env.replay_loss_metadata()['target_deviation'],checked_unix=time.time())
(p.out/'limp-radius-termination-test.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
