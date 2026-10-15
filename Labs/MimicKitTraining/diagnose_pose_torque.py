"""Bounded first-invalid-step diagnosis; no optimization, uploads or runtime edits."""
import os,sys,json,collections,time
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
ROOT=Path('/workspace/mimickit_trial');sys.path.insert(0,str(ROOT/'MimicKit/mimickit'))
import torch,numpy as np,yaml
import run as upstream
from learning.ppo_agent import PPOAgent
from learning.base_agent import AgentMode
from world_pose import WorldPoseEnv
from networks import register_network

def main():
    d=Path(sys.argv[1]);out=Path(sys.argv[2]);zero='--zero' in sys.argv
    torch.set_num_threads(1);torch.manual_seed(20261014);np.random.seed(20261014);os.chdir(ROOT/'MimicKit')
    upstream.mp_util.init(0,1,'cuda:0',6750);register_network()
    cfg,ecfg,acfg=[yaml.safe_load((d/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    if '--sim-freq' in sys.argv:
        ecfg['sim_freq']=int(sys.argv[sys.argv.index('--sim-freq')+1])
    if '--integrator' in sys.argv:
        import engines.newton_engine as ne
        requested_integrator=sys.argv[sys.argv.index('--integrator')+1]
        def build_solver(engine):
            engine._solver=ne.newton.solvers.SolverMuJoCo(engine._sim_model,solver='newton',
                njmax=450,nconmax=150,impratio=10,iterations=100,ls_iterations=50,integrator=requested_integrator)
        ne.NewtonEngine._build_solver=build_solver
    env=WorldPoseEnv(cfg,ecfg,512,'cuda:0',False);agent=PPOAgent(acfg,env,'cuda:0');agent.eval();agent.set_mode(AgentMode.TRAIN)
    eng=env._engine;char=env._get_char_id();obs,info=env.reset();history=collections.deque(maxlen=6);resets=torch.zeros(512,device='cuda:0',dtype=torch.long)
    started=time.perf_counter();report=dict(zero_action=zero,sim_freq=ecfg['sim_freq'],failed=False)
    model=eng._solver.mj_model
    import warp as wp,mujoco
    if '--capture-mujoco' in sys.argv:mujoco.mj_saveModel(model,str(out.with_suffix('.mjb')),None)
    report['model']=dict(integrator=int(model.opt.integrator),joint_names=[model.joint(i).name for i in range(model.njnt)],
        joint_limited=model.jnt_limited.tolist(),dof_armature=model.dof_armature.tolist(),dof_damping=model.dof_damping.tolist(),
        body_mass=model.body_mass.tolist(),body_inertia=model.body_inertia.tolist())
    with torch.no_grad():
        for tick in range(240):
            action=torch.zeros((512,28),device='cuda:0') if zero else agent._decide_action(obs,info)[0]
            if '--cutoff' in sys.argv and tick>=int(sys.argv[sys.argv.index('--cutoff')+1]):action.zero_()
            before=dict(body=eng.get_body_pos(char).clone(),rot=eng.get_body_rot(char).clone(),vel=eng.get_dof_vel(char).clone(),dof=eng.get_dof_pos(char).clone(),action=action.clone(),resets=resets.clone(),episode_tick=env._timestep_buf.clone())
            if '--capture-mujoco' in sys.argv:
                before['mj_qpos']=wp.to_torch(eng._solver.mjw_data.qpos).clone()
                before['mj_qvel']=wp.to_torch(eng._solver.mjw_data.qvel).clone()
            obs,reward,done,info=env.step(action)
            if '--capture-mujoco' in sys.argv:
                before['mj_applied']=wp.to_torch(eng._solver.mjw_data.qfrc_applied).clone()
            finite=torch.isfinite(obs).all(-1)&torch.isfinite(reward)
            history.append(before)
            if not finite.all():
                ids=(~finite).nonzero().flatten();world=int(ids[0]);records=[];arrays={}
                for k,h in enumerate(history):
                    records.append(dict(episode_tick=int(h['episode_tick'][world]),reset_count=int(h['resets'][world]),max_action=float(h['action'][world].abs().max()),max_dof_velocity=float(h['vel'][world].abs().max()),root=h['body'][world,0].cpu().tolist(),quat_norm_range=[float(h['rot'][world].norm(dim=-1).min()),float(h['rot'][world].norm(dim=-1).max())]))
                    for name,value in h.items():arrays[f'{k}_{name}']=value[world].cpu().numpy()
                arrays['failed_body']=eng.get_body_pos(char)[world].cpu().numpy();arrays['failed_rot']=eng.get_body_rot(char)[world].cpu().numpy();arrays['failed_vel']=eng.get_dof_vel(char)[world].cpu().numpy()
                report.update(failed=True,tick=tick+1,world=world,invalid_worlds=ids.cpu().tolist(),history=records,
                    action_finite=bool(torch.isfinite(action[world]).all()),body_finite=bool(torch.isfinite(eng.get_body_pos(char)[world]).all()),rot_finite=bool(torch.isfinite(eng.get_body_rot(char)[world]).all()),velocity_finite=bool(torch.isfinite(eng.get_dof_vel(char)[world]).all()))
                np.savez_compressed(out.with_suffix('.npz'),**arrays);break
            ids=(done!=0).nonzero().flatten();resets[ids]+=1;obs,info=env.reset(ids)
        report.update(completed_ticks=tick+1,elapsed_seconds=time.perf_counter()-started,resets=int(resets.sum()))
    out.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
