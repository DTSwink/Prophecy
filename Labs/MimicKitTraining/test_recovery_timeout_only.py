"""Recovery-only termination override and unchanged ordinary rows."""
from diagnose_floor_guard_speed import *
from unittest.mock import patch
from omni_walk import OmniWalkEnv
from envs.base_env import DoneFlags

def unit():
    stub=object.__new__(RecoveryOmniEnv)
    stub.__dict__.update(_recovery_ready=True,_recovery_timeout_only=True,_recovery_sphere_only=False,
        _reset_after_getup=False,
        _recovery_ids=torch.tensor([0,2,3]),_episode_length=10.,
        _time_buf=torch.tensor([.5,.5,9.99,10.]),_done_buf=torch.ones(4,dtype=torch.int32),
        _get_char_id=lambda:0)
    with patch.object(OmniWalkEnv,'_update_done',lambda self:None):
        RecoveryOmniEnv._update_done(stub)
    assert stub._done_buf.tolist()==[0,1,0,3]
    stub._reset_after_getup=True
    stub.recovery_active=lambda:torch.tensor([True,True,False,False])
    with patch.object(OmniWalkEnv,'_update_done',lambda self:None):
        RecoveryOmniEnv._update_done(stub)
    assert stub._done_buf.tolist()==[0,1,3,3]
    stub._recovery_sphere_only=True;stub._recovery_timeout_only=False
    stub._recovery_target_indices=list(range(5));stub._target_radius_sq=torch.tensor(.30).square()
    stub.target_distances_sq=torch.zeros(4,5)
    for body in range(5):
        stub.target_distances_sq.zero_();stub.target_distances_sq[0,body]=stub._target_radius_sq
        with patch.object(OmniWalkEnv,'_update_done',lambda self:None):RecoveryOmniEnv._update_done(stub)
        assert stub._done_buf[0]==0
        stub.target_distances_sq[0,body]=.301**2
        with patch.object(OmniWalkEnv,'_update_done',lambda self:None):RecoveryOmniEnv._update_done(stub)
        assert stub._done_buf[0]==1
    stub._absolute_recovery=False
    reference=torch.randn(4,15,3)
    actual=reference+torch.tensor([2.,-3.,.4])
    target=RecoveryOmniEnv._target_positions(stub,actual,reference)
    torch.testing.assert_close(target[:,:,:2],reference[:,:,:2]+torch.tensor([2.,-3.]))
    torch.testing.assert_close(target[:,:,2],reference[:,:,2])
    torch.testing.assert_close(RecoveryOmniEnv._target_positions(stub,actual[[0,2]],reference[[0,2]],torch.tensor([0,2])),target[[0,2]])

unit()
if '--unit-only' in sys.argv:
    print('Recovery termination and pelvis XY target checks passed');sys.exit(0)
torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6798)
folder=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
fresh='--fresh-idle-only' in sys.argv
clip_end='--clip-end' in sys.argv
sphere='--sphere30' in sys.argv
cfg['idle_row_fraction']=1. if fresh else .18
cfg['idle_recovery'].update(timeout_only=True,absolute_target=False,reset_at_getup_end=clip_end)
if fresh:cfg['idle_recovery']['fraction']=1.
if sphere:
    cfg['target_radius_m']=.30
    cfg['idle_recovery'].update(timeout_only=False,sphere_only=True,target_termination_bodies=['head','right_hand','left_hand','right_foot','left_foot'])
os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False)
agent=OmniPPOAgent(ac,env,'cuda:0')
receipt=dict(prior_samples=0,iteration_offset=0) if fresh else restore(agent,ROOT/'Saved/MimicKitEquipment/idle18-resume-latest.zip')
agent.eval();agent.set_mode(AgentMode.TEST)
obs,info=env.reset()
for _ in range(8):
    with torch.no_grad():action,_=agent._decide_action(obs,info);obs,_,done,info=env.step(action)
    if sphere:
        failed=(env.target_distances_sq>env._target_radius_sq).any(-1)&(env._time_buf>0)
        assert torch.equal(done==DoneFlags.FAIL.value,failed)
        assert torch.equal(done==DoneFlags.TIME.value,(~env.recovery_active())&(~failed))
    else:assert not bool((done[env._recovery_ids]==DoneFlags.FAIL.value).any())
    if clip_end and not sphere:
        assert torch.equal(done[env._recovery_ids]==DoneFlags.TIME.value,~env.recovery_active()[env._recovery_ids])
        assert bool(env.recovery_reference_active()[env._recovery_ids].all())
    elif not sphere:assert not bool(done[env._recovery_ids].any())
    ids=torch.nonzero(done,as_tuple=False).flatten()
    if len(ids):obs,info=env.reset(ids)
assert torch.isfinite(obs).all()
env._time_buf[env._recovery_ids]=env._episode_length
if sphere:env._recovery_sphere_only=False;env._recovery_timeout_only=True
env._update_done()
assert bool((env._done_buf[env._recovery_ids]==DoneFlags.TIME.value).all())
count=512 if fresh else 74
assert env._reset_after_getup==clip_end and len(env._recovery_ids)==count
if fresh:assert bool((env._gaits[env._fixed_motion_ids]==-1).all())
report=dict(passed=True,resume=receipt,recovery_rows=count,horizon_seconds=env._episode_length,physics_ticks=8,reset_at_getup_end=clip_end,sphere_radius_m=.30 if sphere else None)
(ROOT/'Saved/MimicKitEquipment'/('sphere30-smoke.json' if sphere else 'fresh-clip-end-smoke.json' if clip_end else 'fresh-idle-smoke.json' if fresh else 'timeout-only-smoke.json')).write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
