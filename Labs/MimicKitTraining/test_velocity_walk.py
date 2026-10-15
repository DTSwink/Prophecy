"""Bounded stock DeepMimic velocity smoke test; no optimizer steps or training edits."""
import os,sys,json,tempfile
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial')
sys.path.insert(0,str(ROOT/'MimicKit/mimickit'))
import torch,yaml,numpy as np
import run as upstream
from learning.base_agent import AgentMode
from observe import Recorder

def main():
    torch.set_num_threads(1);os.chdir(ROOT/'MimicKit')
    cfg=yaml.safe_load(Path('data/envs/deepmimic_humanoid_env.yaml').read_text())
    cfg['motion_file']='data/motions/humanoid/humanoid_walk.pkl'
    eng=yaml.safe_load(Path('data/engines/newton_engine.yaml').read_text());eng['control_mode']='vel'
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);(d/'env.yaml').write_text(yaml.safe_dump(cfg));(d/'engine.yaml').write_text(yaml.safe_dump(eng))
        args=upstream.load_args(['train','--env_config',str(d/'env.yaml'),'--engine_config',str(d/'engine.yaml'),
            '--agent_config','data/agents/deepmimic_humanoid_ppo_agent.yaml','--rand_seed','20261014','--visualize','false','--logger','tb'])
        upstream.mp_util.init(0,1,'cuda:0',6742);upstream.set_rand_seed(args)
        env=upstream.build_env(args,512,'cuda:0',False);agent=upstream.build_agent(args,env,'cuda:0')
        agent.eval();agent.set_mode(AgentMode.TEST);engine=env._engine;char=env._get_char_id()
        obs,info=env.reset()
        assert engine.get_control_mode().name=='vel'
        assert np.all(engine._sim_model.joint_target_ke.numpy()==0)
        assert np.max(engine._sim_model.joint_target_kd.numpy())>0
        limits=torch.as_tensor(engine.get_obj_torque_limits(0,char),device='cuda:0')
        assert limits.numel()==28 and torch.isfinite(limits).all() and (limits>0).all()
        torch.testing.assert_close(env._action_bound_high,torch.full_like(env._action_bound_high,2*np.pi))
        zero=torch.zeros((512,28),device='cuda:0');env._apply_action(zero)
        assert (engine._controls.target_vel[char]==0).all()
        # Identical airborne pairs isolate commanded torque from ground contact.
        ids=torch.arange(512,device='cuda:0')
        for getter,setter in [('get_root_pos','set_root_pos'),('get_root_rot','set_root_rot'),('get_dof_pos','set_dof_pos')]:
            values=getattr(engine,getter)(char)[0:1].expand(512,-1).clone()
            if getter=='get_root_pos':values[:,2]+=2.
            getattr(engine,setter)(ids,char,values)
        engine.set_root_vel(ids,char,0.);engine.set_root_ang_vel(ids,char,0.);engine.set_dof_vel(ids,char,0.)
        engine.set_body_vel(ids,char,0.);engine.set_body_ang_vel(ids,char,0.)
        env._reset_char_rigid_body_state(ids)
        cmd=zero.clone();cmd[256:,0]=1.0
        env.step(cmd)
        torch.testing.assert_close(engine._controls.target_vel[char],cmd)
        response=float((engine.get_dof_vel(char)[256:]-engine.get_dof_vel(char)[:256]).abs().max())
        assert response>1e-4,'Nonzero velocity target must affect physical joint velocity'
        with torch.no_grad():
            obs,info=env.reset();rec=Recorder(env,d);rec.start();ended=0
            for tick in range(90):
                action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
                assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
                assert torch.isfinite(engine.get_body_pos(char)).all()
                ids=(done!=0).nonzero().flatten();ended+=len(ids)
                obs,info=env.reset(ids)
            meta=rec.finish(0,0,dict(control_mode='vel',worlds=512))
            assert meta['complete_episode'] and ended>0
        report=dict(passed=True,worlds=512,action_dofs=28,torque_limits_nm=limits.tolist(),
            position_gain_zero=True,velocity_gain_positive=True,zero_command_zero_velocity_target=True,action_bound_rad_s=2*np.pi,
            velocity_command_response_rad_s=response,finite_policy_ticks=90,ended_episodes=ended,
            replay_frames=int(round(meta['duration_seconds']*30))+1,stock_task='deepmimic humanoid_walk',optimizer_steps=0)
    (ROOT/'velocity-smoke.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
