"""Same pose objective with stock DeepMimic PPO and fresh direct-torque actions."""
import os,sys,json,zipfile,tempfile,time
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial')
sys.path.insert(0,str(ROOT/'MimicKit/mimickit'))
import torch,numpy as np,yaml
import run as upstream
from learning.ppo_agent import PPOAgent
from learning.base_agent import AgentMode
from networks import register_network
from world_pose import WorldPoseEnv,world_pose_mse,height_band_mse
from observe import Recorder

def main():
    started=time.perf_counter();torch.set_num_threads(1);torch.manual_seed(20261014);os.chdir(ROOT/'MimicKit');upstream.mp_util.init(0,1,'cuda:0',6748);register_network()
    with zipfile.ZipFile(sys.argv[1]) as z:
        cfg,ecfg,prior_agent=[yaml.safe_load(z.read(n+'_config.yaml')) for n in ('env','engine','agent')]
    for k in ('floor_impact_limit_n','floor_impact_bodies'):cfg.pop(k,None)
    ecfg.pop('track_ground_contact_peaks',None);ecfg['control_mode']='torque'
    acfg=yaml.safe_load(Path('data/agents/deepmimic_humanoid_ppo_agent.yaml').read_text())
    acfg['model'].update(actor_net='fc_1024_1024',critic_net='fc_1024_1024');acfg['iters_per_log']=prior_agent['iters_per_log']
    assert acfg==prior_agent,'PPO settings must match previous experiment exactly'
    env=WorldPoseEnv(cfg,ecfg,512,'cuda:0',False);agent=PPOAgent(acfg,env,'cuda:0');agent.eval();agent.set_mode(AgentMode.TEST)
    engine=env._engine;char=env._get_char_id();obs,info=env.reset()
    assert obs.shape==(512,140) and agent._sample_count==0 and not hasattr(agent,'_disc_optimizer')
    assert 'envs.amp_env' not in sys.modules and 'learning.amp_agent' not in sys.modules
    assert engine.get_control_mode().name=='torque' and not engine._track_ground_contact_peaks
    assert not hasattr(engine,'_ground_peak_buffer') and env.floor_impact_limit_n is None
    assert np.all(engine._sim_model.joint_target_ke.numpy()==0) and np.all(engine._sim_model.joint_target_kd.numpy()==0)
    assert env.loss_term_names==('body_pose_mse','head_height_band','pelvis_height_band','termination_remaining')
    assert abs(env._feet_max_width-.448225274682045)<1e-7
    limits=torch.as_tensor(engine.get_obj_torque_limits(0,char),device='cuda:0');torch.testing.assert_close(env._action_bound_high,limits)
    zero=torch.zeros((512,28),device='cuda:0');env._apply_action(zero);assert (engine.get_dof_forces(char)==0).all()
    response=None
    if '--skip-air-probe' not in sys.argv:
        ids=torch.arange(512,device='cuda:0')
        for getter,setter in [('get_root_pos','set_root_pos'),('get_root_rot','set_root_rot'),('get_dof_pos','set_dof_pos')]:
            values=getattr(engine,getter)(char)[0:1].expand(512,-1).clone()
            if getter=='get_root_pos':values[:,2]+=2.
            getattr(engine,setter)(ids,char,values)
        engine.set_root_vel(ids,char,0.);engine.set_root_ang_vel(ids,char,0.);engine.set_dof_vel(ids,char,0.)
        engine.set_body_vel(ids,char,0.);engine.set_body_ang_vel(ids,char,0.);env._reset_char_rigid_body_state(ids)
        cmd=zero.clone();cmd[256:,0]=limits[0]*.25;env.step(cmd)
        torch.testing.assert_close(engine.get_dof_forces(char),cmd)
        response=float((engine.get_dof_vel(char)[256:]-engine.get_dof_vel(char)[:256]).abs().max());assert response>1e-4
    obs,info=env.reset();back=int(env._starts_on_back.sum());assert 180<back<330
    p=engine.get_body_pos(char);q=engine.get_body_rot(char);env._timestep_buf[:]=1;env._time_buf[:]=1/30;env._update_reward()
    expected=world_pose_mse(p,q,env._target_positions,env._target_rotations,True).sum(-1)/60
    torch.testing.assert_close(env.loss_terms[:,0],expected)
    torch.testing.assert_close(env.loss_terms[:,1:3],height_band_mse(p[:,env._height_body_ids,2],env._target_positions[:,env._height_body_ids,2])*env._height_weights/60)
    assert not env._impact_failed.any()
    with tempfile.TemporaryDirectory() as tmp,torch.no_grad():
        obs,info=env.reset();rec=Recorder(env,tmp);rec.start();ended=0
        for tick in range(60):
            action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
            if not (torch.isfinite(obs).all() and torch.isfinite(reward).all()):
                diagnostic=dict(tick=tick+1,action_finite=bool(torch.isfinite(action).all()),max_action=float(action.abs().max()),
                    nonfinite_obs=torch.nonzero(~torch.isfinite(obs)).cpu().tolist()[:20],nonfinite_rewards=int((~torch.isfinite(reward)).sum()),
                    body_pos_finite=bool(torch.isfinite(engine.get_body_pos(char)).all()),dof_vel_finite=bool(torch.isfinite(engine.get_dof_vel(char)).all()),
                    max_finite_dof_vel=float(torch.nan_to_num(engine.get_dof_vel(char),nan=0,posinf=0,neginf=0).abs().max()))
                Path(sys.argv[2]).with_suffix('.failure.json').write_text(json.dumps(diagnostic,indent=2));raise AssertionError(diagnostic)
            torch.testing.assert_close(reward,-env.loss_terms.sum(-1))
            torch.testing.assert_close(env.loss_terms[:,-1],torch.where(env._feet_failed,env.loss_terms[:,:3].sum(-1)*(60-env._timestep_buf).clamp_min(0),0.))
            ids=(done!=0).nonzero().flatten();ended+=len(ids);obs,info=env.reset(ids)
        meta=rec.finish(0,0,dict(control_mode='torque'))
        assert 'floor_impact_limit_n' not in meta and 'frame_floor_peak_n' not in meta and meta['control_mode']=='torque'
        assert meta['loss_term_names']==list(env.loss_term_names)
    report=dict(passed=True,worlds=512,inputs=140,actions=28,network=[1024,1024],ppo_config_exact_match=True,
        no_amp_modules=True,no_impact_measurement=True,zero_position_and_velocity_gains=True,zero_command_zero_torque=True,
        torque_limits_nm=limits.tolist(),torque_response_rad_s=response,unchanged_pose_height_losses=True,
        foot_limit_m=env._feet_max_width,remaining_charge=True,back_starts=back,finite_ticks=60,completed_episodes=ended,
        fresh_samples=agent._sample_count,seconds=time.perf_counter()-started)
    Path(sys.argv[2]).write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
