"""Verify native velocity servos and unchanged pose task before a fresh run."""
import os,sys,json,time
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial');sys.path.insert(0,str(ROOT/'MimicKit/mimickit'))
import torch,numpy as np,yaml
import run as upstream
from learning.ppo_agent import PPOAgent
from learning.base_agent import AgentMode
from networks import register_network
from world_pose import WorldPoseEnv,world_pose_mse,height_band_mse

def main():
    torch.set_num_threads(1);torch.manual_seed(20261014);np.random.seed(20261014)
    os.chdir(ROOT/'MimicKit');upstream.mp_util.init(0,1,'cuda:0',6751);register_network()
    prior=Path(sys.argv[1]);out=Path(sys.argv[2]);started=time.perf_counter()
    cfg,ecfg,acfg=[yaml.safe_load((prior/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    ecfg['control_mode']='vel'
    env=WorldPoseEnv(cfg,ecfg,512,'cuda:0',False);agent=PPOAgent(acfg,env,'cuda:0')
    agent.eval();agent.set_mode(AgentMode.TRAIN);eng=env._engine;char=env._get_char_id()
    assert eng.get_control_mode().name=='vel' and ecfg['sim_freq']==240
    assert np.all(eng._sim_model.joint_target_ke.numpy()==0)
    gains=eng._sim_model.joint_target_kd.numpy();assert gains.max()>0
    assert not eng._track_ground_contact_peaks and env.floor_impact_limit_n is None
    assert not hasattr(agent,'_disc_optimizer') and 'envs.amp_env' not in sys.modules
    obs,info=env.reset();assert obs.shape==(512,140) and agent._sample_count==0
    torch.testing.assert_close(env._action_bound_high,torch.full((28,),2*np.pi,device='cuda:0'))
    assert abs(env._feet_max_width-.448225274682045)<1e-7
    ids=torch.arange(512,device='cuda:0')
    for getter,setter in [('get_root_pos','set_root_pos'),('get_root_rot','set_root_rot'),('get_dof_pos','set_dof_pos')]:
        values=getattr(eng,getter)(char)[0:1].expand(512,-1).clone()
        if getter=='get_root_pos':values[:,2]+=2.
        getattr(eng,setter)(ids,char,values)
    eng.set_root_vel(ids,char,0.);eng.set_root_ang_vel(ids,char,0.)
    vel=torch.zeros((512,28),device='cuda:0');vel[:,0]=2.
    eng.set_dof_vel(ids,char,vel);env._reset_char_rigid_body_state(ids)
    cmd=torch.zeros_like(vel);cmd[256:,0]=2.;env.step(cmd)
    torch.testing.assert_close(eng._controls.target_vel[char],cmd)
    response=float((eng.get_dof_vel(char)[256:,0]-eng.get_dof_vel(char)[:256,0]).mean())
    assert response>0.1,'A positive velocity target must produce more positive speed than zero target'
    obs,info=env.reset();ended=0;max_speed=0.;roll_start=time.perf_counter()
    with torch.no_grad():
        for tick in range(240):
            action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
            assert torch.isfinite(obs).all() and torch.isfinite(reward).all(),f'Nonfinite tick {tick+1}'
            p,q=eng.get_body_pos(char),eng.get_body_rot(char)
            torch.testing.assert_close(env.loss_terms[:,0],world_pose_mse(p,q,env._target_positions,env._target_rotations,True).sum(-1)/60)
            torch.testing.assert_close(env.loss_terms[:,1:3],height_band_mse(p[:,env._height_body_ids,2],env._target_positions[:,env._height_body_ids,2])*env._height_weights/60)
            torch.testing.assert_close(env.loss_terms[:,-1],torch.where(env._feet_failed,env.loss_terms[:,:3].sum(-1)*(60-env._timestep_buf).clamp_min(0),0.))
            torch.testing.assert_close(reward,-env.loss_terms.sum(-1))
            max_speed=max(max_speed,float(eng.get_dof_vel(char).abs().max()))
            ids=(done!=0).nonzero().flatten();ended+=len(ids);obs,info=env.reset(ids)
    report=dict(passed=True,worlds=512,finite_stochastic_ticks=240,fresh_samples=agent._sample_count,
        control_mode='vel',sim_freq=240,command_limit_rad_s=2*np.pi,velocity_gain_range=[float(gains[gains>0].min()),float(gains.max())],
        position_gain_zero=True,velocity_response_rad_s=response,max_measured_dof_speed_rad_s=max_speed,
        unchanged_losses=True,foot_limit_m=env._feet_max_width,completed_episodes=ended,
        rollout_seconds=time.perf_counter()-roll_start,total_seconds=time.perf_counter()-started)
    out.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
