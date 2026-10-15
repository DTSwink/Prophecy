"""Verify strict lateral-spread failure, unchanged losses, reset and replay semantics."""
import os,sys,io,json,zipfile,tempfile
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial')
sys.path.insert(0,str(ROOT/'MimicKit/mimickit'))
import torch,numpy as np,yaml
import run as upstream
from learning.ppo_agent import PPOAgent
from learning.base_agent import AgentMode
from amp_standing import register_network
from world_pose import WorldPoseEnv,lateral_foot_separation,world_pose_mse,height_band_mse
from util import torch_util
from observe import Recorder
from replay import convert,geometry


def main():
    archive=Path(sys.argv[1]);destination=Path(sys.argv[2])
    with zipfile.ZipFile(archive) as z:
        cfg=yaml.safe_load(z.read('env_config.yaml'));engine=yaml.safe_load(z.read('engine_config.yaml'))
        acfg=yaml.safe_load(z.read('agent_config.yaml'))
        model=torch.load(io.BytesIO(z.read('model.pt')),map_location='cuda:0',weights_only=True)
    assert 'feet_lateral_calibration' in cfg
    cfg['feet_lateral_termination']=True
    valid_pool='--valid-pool' in sys.argv
    if valid_pool:cfg['valid_reset_pose_pool']=True
    remaining_cost='--remaining-cost' in sys.argv
    if remaining_cost:cfg['termination_remaining_cost']=True
    isotropic='--isotropic' in sys.argv
    if isotropic:cfg['feet_distance_multiple']=1.75
    torch.set_num_threads(1);torch.manual_seed(20261015)
    upstream.mp_util.init(0,1,'cuda:0',6741);register_network();os.chdir(ROOT/'MimicKit')
    env=WorldPoseEnv(cfg,engine,512,'cuda:0',False)
    agent=PPOAgent(acfg,env,'cuda:0');agent.load_state_dict(model);agent.eval();agent.set_mode(AgentMode.TEST)
    assert env.loss_term_names==('body_pose_mse','head_height_band','pelvis_height_band')+(('termination_remaining',) if remaining_cost else ())
    assert env.get_reward_fail()==0 and agent._compute_fail_val()==0
    assert env.loss_weights==dict(zip(env.loss_term_names,[1.,*cfg['height_band_weights']]+([1.] if remaining_cost else [])))
    li,ri,pi=env._left_foot_id,env._right_foot_id,env._pelvis_id;limit=env._feet_max_width
    pool_checks=None
    if isotropic:
        obs,info=env.reset()
        p0=env._engine.get_body_pos(env._get_char_id()).clone();q0=env._engine.get_body_rot(env._get_char_id()).clone()
        delta=p0[:,li]-p0[:,ri]
        torch.testing.assert_close(env._foot_separation(p0,q0),delta.square().sum(-1).sqrt())
        # Axis permutations/sign changes preserve distance; pelvis orientation is irrelevant.
        p1=p0[:,:,[2,0,1]]*torch.tensor([-1.,1.,-1.],device='cuda:0')+10.
        torch.testing.assert_close(env._foot_separation(p0,q0),env._foot_separation(p1,q0),atol=2e-6,rtol=0)
        for axis in range(3):
            p1.zero_();p1[:,li,axis]=limit+.001
            assert (env._foot_separation(p1,q0)>limit).all()
        assert abs(limit/env._feet_reference_distance-1.75)<1e-7
    if valid_pool:
        original_fk=env._kin_char_model.forward_kinematics
        # Only the upstream body-state synchronization may run FK. Pool selection
        # must not recompute candidates or floor clearance on each reset.
        fk_calls=[]
        def counted(*args,**kwargs):
            import inspect
            assert inspect.currentframe().f_back.f_code.co_name=='_reset_char_rigid_body_state'
            fk_calls.append(1)
            return original_fk(*args,**kwargs)
        env._kin_char_model.forward_kinematics=counted
        over=0;back_total=0;max_width=0.
        try:
            for _ in range(32):
                env.reset()
                pos=env._engine.get_body_pos(env._get_char_id());rot=env._engine.get_body_rot(env._get_char_id())
                width=env._foot_separation(pos,rot)
                over+=int((width>limit).sum());back_total+=int(env._starts_on_back.sum())
                max_width=max(max_width,float(width.max()))
                assert torch.isfinite(pos).all()
                torch.testing.assert_close(env._lowest_geometry(pos,rot),torch.full((512,),env._floor_clearance,device='cuda:0'),atol=2e-6,rtol=0)
                before=pos[1:].clone();env.reset(torch.tensor([0],device='cuda:0'))
                torch.testing.assert_close(env._engine.get_body_pos(env._get_char_id())[1:],before)
        finally:env._kin_char_model.forward_kinematics=original_fk
        assert over==0 and .45<back_total/(32*512)<.55
        pool_checks=dict(**env.reset_pose_pool_report,resets=32*512,invalid_starts=over,
            back_starts=back_total,max_observed_width_m=max_width,pool_sampling_fk_calls=0,
            upstream_body_sync_fk_calls=len(fk_calls),ground_clearance=True,partial_reset_isolation=True)
    # Inject exact body tensors ONLY for the reward/done check, without modifying
    # the physical engine: below/equal/above, forward separation and crossing.
    obs,info=env.reset();assert obs.shape==(512,140)
    pos=env._engine.get_body_pos(env._get_char_id()).clone()
    rot=env._engine.get_body_rot(env._get_char_id()).clone()
    rot[:,pi]=torch.tensor([0.,0.,0.,1.],device='cuda:0')
    pos[:,li]=0;pos[:,ri]=0
    pos[0,li,1]=limit-.001;pos[1,li,1]=limit;pos[2,li,1]=limit+.001
    pos[3,li,0]=10.;pos[4,li,1]=-limit-.001
    gp,gr=env._engine.get_body_pos,env._engine.get_body_rot
    env._engine.get_body_pos=lambda char:pos
    env._engine.get_body_rot=lambda char:rot
    try:
        env._timestep_buf[:]=1;env._time_buf[:]=1/30
        env._update_reward();env._update_done()
        assert env._done_buf[:5].tolist()==[0,0,1,1 if isotropic else 0,1]
        assert int(env._completed_loss_totals[-1])==(3 if isotropic else 2)
        if remaining_cost:
            torch.testing.assert_close(env.loss_terms[:,-1],torch.where(env._feet_failed,env.loss_terms[:,:3].sum(-1)*59,0.))
            # Constant pose: early failure pays the same full-horizon cost.
            torch.testing.assert_close(env.loss_terms[2].sum(),env.loss_terms[2,:3].sum()*60)
            env._timestep_buf[:]=30;env._update_reward()
            torch.testing.assert_close(env.loss_terms[:,-1],torch.where(env._feet_failed,env.loss_terms[:,:3].sum(-1)*30,0.))
            env._timestep_buf[:]=60;env._update_reward()
            assert (env.loss_terms[:,-1]==0).all()
        torch.testing.assert_close(env._reward_buf,-env.loss_terms.sum(-1))
        env._feet_failed.zero_();env._timestep_buf[:]=60;env._time_buf[:]=2.
        pos[:,li]=pos[:,ri]
        env._update_reward();env._update_done();assert (env._done_buf==3).all()
    finally:
        env._engine.get_body_pos=gp;env._engine.get_body_rot=gr
    env._completed_loss_totals.zero_()
    failure_count=0;timeout_count=0;episode_sums=torch.zeros_like(env.loss_terms)
    completed=torch.zeros(len(env.loss_term_names),device='cuda:0');count=0
    with tempfile.TemporaryDirectory() as tmp,torch.no_grad():
        obs,info=env.reset();rec=Recorder(env,tmp);rec.start()
        initial_width=env._foot_separation(gp(env._get_char_id()),gr(env._get_char_id()))
        initial_stats=dict(over_limit=int((initial_width>limit).sum()),min_m=float(initial_width.min()),
            median_m=float(initial_width.median()),max_m=float(initial_width.max()))
        if valid_pool:assert initial_stats['over_limit']==0
        for tick in range(60):
            action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
            pos=gp(env._get_char_id());rot=gr(env._get_char_id())
            width=env._foot_separation(pos,rot)
            if tick==0:
                first_stats=dict(failed=int((done==1).sum()),median_m=float(width.median()),max_m=float(width.max()))
            assert torch.equal(done==1,width>limit)
            pose=world_pose_mse(pos,rot,env._target_positions,env._target_rotations,True).sum(-1)/60
            heights=height_band_mse(pos[:,env._height_body_ids,2],env._target_positions[:,env._height_body_ids,2])*env._height_weights/60
            expected=torch.cat((pose[:,None],heights),-1)
            if remaining_cost:
                extra=torch.where(done==1,expected.sum(-1)*(60-env._timestep_buf).clamp_min(0),0.)
                expected=torch.cat((expected,extra[:,None]),-1)
            torch.testing.assert_close(env.loss_terms,expected)
            torch.testing.assert_close(reward,-expected.sum(-1))
            assert torch.isfinite(obs).all()
            episode_sums+=expected
            ended=done!=0;ids=ended.nonzero().flatten()
            completed+=episode_sums[ended].sum(0);count+=int(ended.sum())
            failure_count+=int((done==1).sum());timeout_count+=int((done==3).sum())
            keep=~ended;untouched=env._episode_losses[keep].clone()
            obs,info=env.reset(ids)
            assert (env._episode_losses[ids]==0).all() and not env._feet_failed[ids].any()
            torch.testing.assert_close(env._episode_losses[keep],untouched)
            episode_sums[ids]=0
        measured=env.take_completed_losses();assert failure_count>0
        for i,key in enumerate(env.loss_term_names):assert abs(measured[key]-float(completed[i]/count))<1e-5
        meta=rec.finish(0,0,dict(training_action_noise_std=.05,rollout_action_noise_std=0.))
        replay=convert(Path(tmp)/'replay.npz',geometry(Path(cfg['char_file'])),'feet-termination-test')
        values=replay['metadata']['evaluation']['frame_losses']
        assert set(values)==set((*env.loss_term_names,'total'))
        np.testing.assert_allclose(values['total'],np.sum([values[n] for n in env.loss_term_names],axis=0),atol=1e-7)
        assert meta['feet_lateral_termination'] and meta['terminal_flag'] in (1,3)
        with np.load(Path(tmp)/'replay.npz') as z:
            p=torch.from_numpy(z['pose']).to('cuda:0');d=z['data']
            w=env._foot_separation(p[:,:,:3],p[:,:,3:]).cpu().numpy()
            assert np.all(w[1:-1]<=limit)
            assert (w[-1]>limit)==(meta['terminal_flag']==1)
            assert np.count_nonzero(d[1:,0])==1
    report=dict(passed=True,worlds=512,inputs=140,threshold_m=limit,strict_boundary=True,isotropic=isotropic,
        reference_distance_m=env._feet_reference_distance if isotropic else None,
        no_foot_loss=True,no_added_failure_cost=not remaining_cost,remaining_cost=remaining_cost,ppo_failure_value=0,unchanged_base_three_terms=True,
        failures=failure_count,timeouts=timeout_count,completed_episodes=count,
        initial_width=initial_stats,first_tick=first_stats,
        valid_reset_pose_pool=pool_checks,
        replay_ticks=len(d)-1,replay_terminal=meta['terminal_flag'],first_episode_only=True,
        partial_resets=True,completed_loss_accounting=True,finite=True)
    destination.write_text(json.dumps(report,indent=2));print('FEET_TERMINATION_PASS',json.dumps(report),flush=True)


if __name__=='__main__':main()
