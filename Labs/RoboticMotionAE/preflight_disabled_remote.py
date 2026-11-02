"""Bounded disposable test on the retained GPU, independent of the live trainer."""
import os,sys,json,time
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
root=Path('/workspace/mimickit_trial');base=root/'disabled-preflight';p=base/'package';out=base/'report'
sys.path[:0]=[str(p/'pipeline'),str(p/'MimicKit/mimickit')]
import numpy as np
import torch,warp as wp,yaml
from slow_loco_disabled import DisabledSlowLocoEnv
from slow_loco_env import SlowLocoEnv
from absolute_walk import AbsoluteWalkEnv
from disabled_limb_rules import valid_codes,LIMBS,limb_bodies,crawl_rate,cohorts
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from util import mp_util,torch_util as q

def main():
    started=time.time();os.chdir(p/'MimicKit');torch.set_num_threads(2);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6778)
    cfg,ec,ac=[yaml.safe_load((out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    cfg['motion_file']=str(out/'prepared/motions.yaml');cfg['omni_manifest']=str(out/'prepared/manifest.json')
    N=2048;env=DisabledSlowLocoEnv(cfg,ec,N,'cuda:0',False);env.reset()
    names=env._kin_char_model.get_body_names();worlds=torch.arange(N,device='cuda:0')
    assert torch.bincount(env._cohort).tolist()==[205,615,614,614]
    for name,x in env.motion_sampling['by_motion_cohort'].items():
        assert x[0] in (20,21)
        if name in ('lying','sitting'):assert x[1:]==[0,0,0]
        else:
            assert all(v in (76,77) for v in x[1:3])
            assert x[3]==0 if name=='crawl' else x[3] in (87,88)
    assert valid_codes('crawl',1)==[4,8] and valid_codes('crawl',2)==[12] and valid_codes('crawl',3)==[]
    assert any(code&3 for code in valid_codes('crawl_idle',1))
    assert env.get_obs_space().shape==(160,)
    assert torch.equal(env._failure_penalty_by_row,torch.where(env._cohort>0,500.,100.))
    assert torch.equal(env._pelvis_window.windows,torch.where(env._fixed_motion_ids<2,130,70))
    print('ENV READY',time.time()-started,flush=True)
    if hasattr(env,'_crawl_forward_values'):
        from slow_loco_disabled import crawl_forward_bonus
        target=env._crawl_cycle_velocity[None]*.5
        assert .23 < float(torch.linalg.vector_norm(target)) < .24
        for fraction,expected in [(0.,0.),(.1,.5),(.5,2.5),(1.,5.),(1.5,2.5),(2.,0.),(-1.,0.)]:
            torch.testing.assert_close(crawl_forward_bonus(target*fraction,target),torch.tensor([expected],device='cuda:0'),atol=2e-6,rtol=1e-5)
        side=torch.stack((-target[:,1],target[:,0]),-1)
        assert float(crawl_forward_bonus(side,target))==0.
        before_codes=env._codes.clone()
        oldvel=env._engine.get_body_vel;raw=oldvel(env._get_char_id()).clone()
        try:
            # Make every pelvis track the cycle target; only the intended rows
            # receive a bonus, irrespective of their current imitation loss.
            b=env._pelvis_id;char=env._get_char_id()
            offset=torch.cross(env._engine.get_body_ang_vel(char)[:,b],q.quat_rotate(env._engine.get_body_rot(char)[:,b],env._body_com[:,b].expand(N,3)),dim=-1)
            raw[:,b,:2]=env._crawl_cycle_velocity[None]*env._rates[:,None]+offset[:,:2]
            env._engine.get_body_vel=lambda *a,**k:raw
            AbsoluteWalkEnv._update_reward(env);base_reward=env._reward_buf.clone()
            env._update_reward();scope=(env._motion_ids==0)&(env._codes==12)&env._injured
            assert scope.any()
            torch.testing.assert_close(env._reward_buf,base_reward+5.*scope,atol=2e-5,rtol=1e-5)
            assert float(env._crawl_forward_values[~scope].abs().max())==0.
        finally:env._engine.get_body_vel=oldvel
        env.take_completed_losses();env.take_reward_diagnostics()
        print('FORWARD REWARD SCOPE AND RESPONSE CHECKED',flush=True)
    def check():
        obs=env._compute_obs();assert torch.isfinite(obs).all()
        torch.testing.assert_close(obs[:,146:154],env._motion_onehot[env._motion_ids])
        torch.testing.assert_close(obs[:,154:158],env._limb_enabled)
        motion_ids,groups,codes,flags,rates,body_mask,motor_mask,termination = [t.cpu().numpy() for t in (env._motion_ids,env._cohort,env._codes,env._limb_enabled,env._rates,env._mse_body_enabled,env._motor_enabled_binary,env._target_termination_enabled)]
        for w in range(N):
            name=env.motion_labels[int(motion_ids[w])];k=int(groups[w]);c=int(codes[w]);dead=[l for l in range(4) if c&(1<<l)]
            assert c in valid_codes(name,k) if k else c==(8 if name.startswith('limpL') else 4 if name.startswith('limpR') else 0)
            assert int((flags[w]==0).sum())==len(dead)
            if name=='crawl':assert c&3==0 and k<3
            expected=crawl_rate(c) if k and name.startswith('crawl') else 1.
            assert abs(float(rates[w])-expected)<1e-6
            assert bool(termination[w,-1])==(name not in ('agonising','agonising_idle'))
            multiplier=2. if k else 1.
            assert abs(float(env._pelvis_window.radius[w])-.40*multiplier)<1e-6
            for l in range(4):
                for body in limb_bodies(l):
                    b=names.index(body);j=env._kin_char_model.get_joint(b)
                    assert bool(body_mask[w,b])==(l not in dead)
                    assert bool((motor_mask[w,j.dof_idx:j.dof_idx+j.get_dof_dim()]==(l not in dead)).all())
                    for i,point in enumerate(env._termination_points):
                        if point['body']==body:assert bool(termination[w,i])==((l not in dead) and name not in ('agonising','agonising_idle'))
        subset=worlds[::3];torch.testing.assert_close(obs[subset],env._compute_obs(subset))
    check()
    for repeat in range(3):
        previous=env._codes.clone();keep=worlds[1::2]
        env.reset(worlds[::2]);check();torch.testing.assert_close(env._codes[keep],previous[keep])
    print('RESETS CHECKED',time.time()-started,flush=True)
    # Vanilla physical initial state equals exact existing reference; no random pose.
    v=~env._injured; char=env._get_char_id()
    torch.testing.assert_close(env._engine.get_dof_pos(char)[v],env._ref_dof_pos[v],atol=1e-5,rtol=1e-5)
    torch.testing.assert_close(env._engine.get_dof_vel(char)[v],env._ref_dof_vel[v])
    # Reference clock, analytic velocities and next-phase prediction all share rate.
    env._time_buf.fill_(.137);env._update_ref_motion()
    times=env._time_buf*env._rates+env._motion_time_offsets
    torch.testing.assert_close(env._get_motion_times(),times)
    vals=env._motion_lib.calc_motion_frame(env._motion_ids,times)
    for dest,index in [(env._ref_root_pos,0),(env._ref_root_rot,1),(env._ref_joint_rot,4)]:torch.testing.assert_close(dest,vals[index])
    for dest,index in [(env._ref_root_vel,2),(env._ref_root_ang_vel,3),(env._ref_dof_vel,5)]:torch.testing.assert_close(dest,vals[index]*env._rates[:,None])
    from omni_walk import phase_at
    torch.testing.assert_close(env.next_phase_target(),phase_at(times,env._motion_lib.get_motion_length(env._motion_ids),env._phase_offsets[env._motion_ids],env._engine.get_timestep()*env._rates))
    env.reset()
    print('CLOCK CHECKED',time.time()-started,flush=True)
    # Every disabled body may have arbitrary position/rotation/velocity without
    # contributing an imitation error. Enabled-body changes must still cost.
    pos=env._engine.get_body_pos(char).clone();rot=env._engine.get_body_rot(char).clone()
    tv,ta=env._world_reference_velocities(env._ref_body_pos,env._ref_body_rot,env._ref_root_vel,env._ref_root_ang_vel,env._ref_dof_vel,env._motion_ids,env._get_motion_times())
    vel=torch.zeros_like(pos);ang=torch.zeros_like(pos)
    before=env._tracking_losses(pos,rot,vel,ang,tv,ta).clone()
    dead=~env._mse_body_enabled
    badpos=torch.where(dead,pos+10,pos);badvel=torch.where(dead,vel+20,vel);badang=torch.where(dead,ang+30,ang)
    other=rot.clone();other[dead[:,:,0]]=torch.tensor([1.,0,0,0],device='cuda:0')
    after=env._tracking_losses(badpos,other,badvel,badang,tv,ta).clone()
    torch.testing.assert_close(before,after)
    vanilla=SlowLocoEnv._tracking_losses(env,pos,rot,vel,ang,tv,ta).clone()
    torch.testing.assert_close(before[v],vanilla[v])
    # Excluding dead mass from the separate COM objective must really work.
    oldvel=env._engine.get_body_vel;rawvel=oldvel(char).clone()
    try:
        env._engine.get_body_vel=lambda *a,**k:rawvel
        a=env._tracking_losses(pos,rot,vel,ang,tv,ta).clone()
        rawvel.add_(dead.to(rawvel.dtype)*200.)
        b=env._tracking_losses(pos,rot,vel,ang,tv,ta).clone()
        torch.testing.assert_close(a[env._injured],b[env._injured])
    finally:env._engine.get_body_vel=oldvel
    print('LOSSES CHECKED',time.time()-started,flush=True)
    # Actual production termination method, every mask/body at its boundary.
    engine=env._engine;oldpos=engine.get_body_pos;oldrot=engine.get_body_rot;oldbase=AbsoluteWalkEnv._update_done
    env._tracking_losses(pos,rot,vel,ang,tv,ta)
    fakepos=env.reward_target_pos.clone();fakerot=env.reward_target_rot.clone();basepos=fakepos.clone()
    engine.get_body_pos=lambda *a,**k:fakepos;engine.get_body_rot=lambda *a,**k:fakerot
    AbsoluteWalkEnv._update_done=lambda self:None
    oldwindowupdate=env._pelvis_window.update
    cases=0
    try:
        for column,point in enumerate(env._termination_points):
            b=names.index(point['body'])
            for delta in (-.001,.001,2.):
                fakepos.copy_(basepos);fakepos[:,b,0]+=env._target_radii_sq[:,column].sqrt()+delta
                env._pelvis_window.reset(worlds,fakepos[:,env._pelvis_id],env._ref_body_pos[:,env._pelvis_id])
                env._done_buf.zero_();env._time_buf.fill_(.1);env._reward_buf.fill_(1.)
                if point['body']=='pelvis':env._pelvis_window.target.copy_(basepos[:,env._pelvis_id]);env._pelvis_window.update=lambda *a:None
                env._update_done();expected=env._target_termination_enabled[:,column]&(delta>0)
                torch.testing.assert_close(env._done_buf==1,expected)
                torch.testing.assert_close(env._reward_buf,1.-torch.where(env._cohort>0,500.,100.)*expected)
                cases+=N
    finally:
        engine.get_body_pos=oldpos;engine.get_body_rot=oldrot;AbsoluteWalkEnv._update_done=oldbase;env._pelvis_window.update=oldwindowupdate
    print('BOUNDARIES CHECKED',time.time()-started,flush=True)
    env.reset();max_torque=0.
    for tick in range(32):
        env.step(torch.full((N,34),3. if tick%2 else -3.,device='cuda:0'))
        torque=env._engine._dof_forces[0]
        max_torque=max(max_torque,float(torque[env._motor_enabled_binary==0].abs().max()))
        assert max_torque<1e-7 and torch.isfinite(torque).all()
        bonus=getattr(env,'_crawl_forward_values',torch.zeros_like(env._reward_buf))
        torch.testing.assert_close(env._reward_buf,torch.exp(-env.loss_terms.sum(-1))+bonus-torch.where(env._cohort>0,500.,100.)*(env._done_buf==1))
        reset=(env._done_buf!=0).nonzero().flatten()
        if len(reset):env.reset(reset)
    check();env._engine.validate_transfer_solver()
    print('PHYSICS CHECKED',time.time()-started,flush=True)
    agent=OmniPPOAgent(ac,env,'cuda:0')
    from resume import restore
    resume=json.loads((base/'preflight_resume.json').read_text())
    import hashlib
    assert hashlib.sha256(Path(resume['path']).read_bytes()).hexdigest()==resume['sha256']
    restored=restore(agent,resume['path'])
    from disabled_limb_rules import migrate_disabled_arm_flags
    normalization=migrate_disabled_arm_flags(agent)
    assert restored['iteration_offset']>0 and restored['optimizer_restored']
    agent._curr_obs,agent._curr_info=agent._reset_envs();agent._init_train()
    agent.eval();agent.set_mode(AgentMode.TRAIN)
    with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
    agent._build_train_data();fail=agent._exp_buffer.get_data('done')==1
    assert fail.any();torch.testing.assert_close(agent._exp_buffer.get_data('tar_val')[fail],agent._exp_buffer.get_data('reward')[fail])
    assert (agent._exp_buffer.get_data('reward')[fail]<=-99.).all()
    agent._update_model();assert all(torch.isfinite(x).all() for x in agent.parameters())
    for extra in range(2):
        agent.eval()
        with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
        agent._build_train_data();agent._update_model()
        assert all(torch.isfinite(x).all() for x in agent.parameters()),extra
    print('RESUMED THREE UPDATES FINITE',time.time()-started,flush=True)
    from observe_many import MultiRecorder
    recorder=MultiRecorder(env,out,33);recorder.phase_agent=agent;original=agent._rollout_test
    def record(n):
        recorder.start()
        try:return original(n)
        finally:recorder.enabled=False
    agent._rollout_test=record;agent.test_model(1)
    replay=recorder.finish(0,0,dict(worlds=N,training_action_noise_std=.05,rollout_action_noise_std=0.))
    from replay import convert
    converted=convert(out/'replay.npz',json.loads((out/'geometry.json').read_text()),'disabled_preflight')
    assert len(converted['rows'])==33
    assert {(r['evaluation']['motion_name'],r['evaluation']['cohort_index']) for r in converted['rows']}=={(n,c) for n in env.motion_labels for c in range(4) if (c==0 or n not in ('lying','sitting')) and not(n=='crawl' and c==3)}
    for row in converted['rows']:
        m=row['evaluation'];assert m['replay_row_label']==row['clip_name']
        expected={b:r for b,r in m['row_target_radii_m'].items() if r is not None}
        assert {x['body']:x['radius_m'] for x in m['target_deviation']['points']}==expected
    from verify_disabled_replay import verify
    independent=verify(out/'replay.npz')
    (out/'independent-replay-checks.json').write_text(json.dumps(independent))
    (out/'preflight.json').write_text(json.dumps(dict(passed=True,worlds=N,observations=160,
        boundary_cases=cases,disabled_torque_max_nm=max_torque,vanilla_equivalent=True,resumed_checkpoint=restored['iteration_offset']-1,normalization=normalization,resumed_updates=3,
        disabled_loss_exclusion=True,clock_velocity_phase_consistent=True,partial_reset_isolated=True,
        ppo_update=True,failure_penalty_and_zero_bootstrap=True,replay_rows=33,
        metadata=env.replay_loss_metadata(),seconds=time.time()-started),indent=2))
    print('PASS disabled curriculum',time.time()-started,flush=True)
if __name__=='__main__':main()
