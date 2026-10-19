"""Bounded physical and phase-transition checks; disposable learner only."""
import os,sys,json,time,io,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
os.environ['PYGLET_HEADLESS']='true'
import torch,warp as wp,yaml
from recovery_omni import RecoveryOmniEnv, rotate_frame
from util import torch_util as q
from omni_policy import OmniPPOAgent,circular_phase
from util import mp_util
from learning.base_agent import AgentMode
from observe_many import MultiRecorder
from resume import restore

def main():
    out=ROOT/'Saved/MimicKitEquipment/recovery-preflight'
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(173)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6791)
    os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
    cfg,ec,ac=[yaml.safe_load((out/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    begun=time.perf_counter();env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False)
    agent=OmniPPOAgent(ac,env,'cuda:0')
    receipt=restore(agent,ROOT/'Saved/MimicKitEquipment/floor-recovery-study-checkpoint.zip')
    agent._curr_obs,agent._curr_info=agent._reset_envs();agent._init_train()
    assert env.get_obs_space().shape==(154,) and env.get_action_space().shape==(34,)
    counts={str(g):int((env._gaits[env._fixed_motion_ids]==g).sum()) for g in (-1,0,1)}
    assert counts['-1']==31 and abs(counts['0']-481*.4)<2 and counts['0']+counts['1']==481,counts
    assert len(env._recovery_ids)==25 and env._adaptive_rows is None
    ids=env._recovery_ids
    assert env._reset_after_getup and env._engine.transfer_floor_guard is not None
    # Retain the previous opt-in transition regression separately, then test
    # the new end-of-clip reset mode used by this launch.
    env._reset_after_getup=False
    # Both front/back must end at the assigned idle's FIRST-frame heading.
    # A rigid yaw must also rotate world velocity and preserve every joint.
    heading_report=[]
    for idle in torch.where(env._gaits == -1)[0].tolist():
        clips=torch.arange(2,device=env._device)
        raw=env._recovery_lib.calc_motion_frame(clips,env._recovery_lib.get_motion_length(clips))
        rotated=rotate_frame(raw,env._recovery_rotation[idle])
        wanted=env._motion_lib.calc_motion_frame(torch.full_like(clips,idle),torch.zeros(2,device=env._device))[1]
        delta=q.calc_heading(rotated[1])-q.calc_heading(wanted)
        torch.testing.assert_close(torch.sin(delta),torch.zeros_like(delta),atol=2e-6,rtol=0)
        assert bool((torch.cos(delta)>.99999).all())
        for k in (4,5):torch.testing.assert_close(rotated[k],raw[k],atol=0,rtol=0)
        torch.testing.assert_close(rotated[0][:,2],raw[0][:,2],atol=2e-6,rtol=0)
        torch.testing.assert_close(rotated[2],q.quat_rotate(env._recovery_rotation[idle],raw[2]))
        p,r=env._kin_char_model.forward_kinematics(raw[0],raw[1],raw[4])
        rp,rr=env._kin_char_model.forward_kinematics(rotated[0],rotated[1],rotated[4])
        torch.testing.assert_close(rp,q.quat_rotate(env._recovery_rotation[idle,:,None].expand(-1,p.shape[1],-1),p),atol=2e-6,rtol=1e-5)
        heading_report.append(dict(idle=idle,rotation_degrees=(q.calc_heading(env._recovery_rotation[idle])*180/torch.pi).tolist()))
    # Get-up reference ignores predictions; input uses them. Queueing must not
    # change the current phase/label before the physics tick.
    env._time_buf.zero_();env._recovery_start[ids]=0
    env._update_ref_motion();original=env._ref_body_pos[ids].clone()
    # Translating the agent must not drag an active get-up target. Ordinary
    # rows still follow XY. Test the same subset path used by reset/replay.
    actual=env._ref_body_pos.clone()+torch.tensor([2.,-3.,.4],device=env._device)
    target=env._target_positions(actual,env._ref_body_pos)
    torch.testing.assert_close(target[ids],original,atol=0,rtol=0)
    torch.testing.assert_close(env._target_positions(actual[ids],original,ids),original,atol=0,rtol=0)
    ordinary=~env._recovery_rows
    torch.testing.assert_close(target[ordinary,:,:2],actual[ordinary,:,:2])
    env._time_buf[ids]=env._recovery_lib.get_motion_length(env._recovery_motion[ids])-1e-4
    assert bool(env.recovery_active()[ids].all())
    env._time_buf[ids]+=1e-4
    assert not bool(env.recovery_active()[ids].any())
    env._update_ref_motion()
    actual=env._ref_body_pos.clone()+torch.tensor([2.,-3.,.4],device=env._device)
    target=env._target_positions(actual,env._ref_body_pos)
    torch.testing.assert_close(target[ids,:,:2],actual[ids,:,:2])
    torch.testing.assert_close(target[ids,:,2],env._ref_body_pos[ids,:,2])
    env._time_buf.zero_();env._update_ref_motion()
    phase_before=env._command_phase()[1].clone();label_before=env.next_phase_target().clone()
    pred=circular_phase(torch.full((25,),.37,device='cuda:0'))
    env.queue_phase_prediction(pred)
    torch.testing.assert_close(env._command_phase()[1],phase_before)
    torch.testing.assert_close(env.next_phase_target(),label_before)
    env._feedback_phase[ids]=env._pending_phase[ids];env._update_ref_motion()
    torch.testing.assert_close(env._ref_body_pos[ids],original)
    torch.testing.assert_close(env._command_phase()[1][ids],pred)
    # Once get-up ends, exact prior-tick phase selects the idle reference.
    env._time_buf[ids]=2.;env._update_ref_motion()
    values=env._motion_lib.calc_motion_frame(env._motion_ids[ids],env._get_motion_times(ids))
    expected,_=env._kin_char_model.forward_kinematics(values[0],values[1],values[4])
    torch.testing.assert_close(env._ref_body_pos[ids],expected)
    torch.testing.assert_close(env.next_phase_target()[ids],circular_phase(.37+env._engine.get_timestep()/env._motion_lib.get_motion_length(env._motion_ids[ids])),atol=2e-6,rtol=1e-5)
    env._reset_after_getup=True
    env._time_buf[ids]=env._recovery_lib.get_motion_length(env._recovery_motion[ids])+1e-4
    env._update_ref_motion()
    final=rotate_frame(env._recovery_lib.calc_motion_frame(env._recovery_motion[ids],env._recovery_lib.get_motion_length(env._recovery_motion[ids])),env._recovery_rotation[env._motion_ids[ids],env._recovery_motion[ids]])
    expected,_=env._kin_char_model.forward_kinematics(final[0],final[1],final[4])
    torch.testing.assert_close(env._ref_body_pos[ids],expected)
    assert bool(env.recovery_reference_active()[ids].all())
    # Many resets include both clips and final frames; physical state and target
    # agree even on direct-to-idle starts. Cohort membership stays fixed.
    starts=[]
    for _ in range(12):
        obs,info=env.reset();starts.extend(env._recovery_motion[ids].cpu().tolist())
        assert torch.equal(env._motion_ids,env._fixed_motion_ids)
        assert torch.isfinite(obs).all()
    assert set(starts)=={0,1}
    agent._curr_obs,agent._curr_info=agent._reset_envs();agent.eval();agent.set_mode(AgentMode.TRAIN)
    original_step=env.step
    def checked_step(action):
        result=original_step(action)
        contact=env._engine.transfer_contact
        errors=wp.to_torch(contact.error)
        if bool((errors!=0).any()):
            import numpy as np
            d=env._engine._solver.mjw_data;m=env._engine._solver.mj_model
            groups=contact.p.manifold
            oversized=np.argwhere(groups.size.numpy()>4)
            pairs=d.contact.geom.numpy();positions=d.contact.pos.numpy();first=groups.first.numpy();count=contact.p.ncontact.numpy();ident=groups.contact_ids.numpy();which=groups.group.numpy()
            details=[]
            for w,g in oversized:
                if g>=groups.count.numpy()[w]:continue
                pair=pairs[first[w,g]]
                details.append(dict(world=int(w),group=int(g),size=int(groups.size.numpy()[w,g]),
                    shapes=[m.geom(int(i)).name for i in pair],positions=[positions[ident[w,c]].tolist() for c in range(count[w]) if which[w,c]==g],
                    time=float(env._time_buf[w]),start=float(env._recovery_start[w]),motion=int(env._recovery_motion[w])))
            (out/'contact-failure.json').write_text(json.dumps(dict(errors=errors.cpu().tolist(),details=details),indent=2))
            raise RuntimeError('Captured first contact failure; see contact-failure.json')
        return result
    env.step=checked_step
    rollout_begun=time.perf_counter()
    with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
    torch.cuda.synchronize();rollout_seconds=time.perf_counter()-rollout_begun
    for value in agent._exp_buffer._buffers.values():assert torch.isfinite(value).all()
    agent._build_train_data();update=agent._update_model()
    assert all(torch.isfinite(p).all() for p in agent.parameters())
    validation=env._engine.validate_transfer_solver()
    # Matched projection cost on an actual post-contact batch. Same qpos and
    # inverse mass for both graph paths; no policy changes or extra PPO updates.
    engine=env._engine;fg=engine.transfer_floor_guard;d=engine._solver.mjw_data
    saved=wp.clone(d.qpos);before=wp.clone(fg.before)
    graphs=[]
    for guarded in (False,True):
        with wp.ScopedCapture(device=env._device) as capture:
            wp.copy(d.qpos,before)
            if guarded:fg.save_before()
            engine.transfer_projection.apply(engine.transfer_contact.p.inv,shared=True)
            if guarded:fg.apply()
        graphs.append(capture.graph)
    measurements={False:[],True:[]}
    for guarded in (False,True,True,False):
        for _ in range(5):wp.capture_launch(graphs[int(guarded)])
        wp.synchronize();began=time.perf_counter()
        for _ in range(30):wp.capture_launch(graphs[int(guarded)])
        wp.synchronize();measurements[guarded].append((time.perf_counter()-began)*1000/30)
    wp.copy(d.qpos,saved)
    projection_timing=dict(original_ms=measurements[False],floor_guard_ms=measurements[True],
        blocked_worlds_last_step=int((fg.fractions.numpy()<1).sum()),rollout_seconds=rollout_seconds)
    recorder=MultiRecorder(env,out,20);recorder.phase_agent=agent
    original_test=agent._rollout_test
    def record(n):
        recorder.start()
        try:return original_test(n)
        finally:recorder.enabled=False
    agent._rollout_test=record
    evaluation=agent.test_model(1)
    replay=recorder.finish(0,0,dict(worlds=512,training_action_noise_std=.05,rollout_action_noise_std=0.))
    rows=replay['replay_rows'];assert any(r.get('recovery_row') for r in rows)
    report=dict(passed=True,counts=counts,recovery_rows=25,normal_idle_rows=6,phase_tests=True,
        restored=receipt,physical_rollout_ticks=32,disposable_ppo_update=True,phase_mse=float(update['phase_prediction_mse']),
        evaluation=evaluation,seconds=time.perf_counter()-begun,replay_rows=len(rows),
        absolute_getup_then_pelvis_relative_idle=True,heading_alignment=heading_report,
        floor_guard=True,reset_at_getup_end=True,projection_timing=projection_timing)
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
if __name__=='__main__':main()
