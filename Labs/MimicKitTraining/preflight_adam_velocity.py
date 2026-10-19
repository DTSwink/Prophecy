"""Discarded 512-world validation of velocity reporting and guarded Adam."""
import os,sys,json,time
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
os.environ['PYGLET_HEADLESS']='true'
import torch,numpy as np,warp as wp,yaml,mujoco
from recovery_omni import RecoveryOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
from util import mp_util
from learning.base_agent import AgentMode


def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6792)
    os.chdir(ROOT/'MimicKit')
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False);engine=env._engine
    agent=OmniPPOAgent(ac,env,'cuda:0');receipt=restore(agent,ROOT/'resume.zip')
    assert receipt['optimizer_restored_by_part']==dict(actor=False,critic=False)
    assert receipt['iteration_offset']==38800 and receipt['prior_samples']==635699200
    assert not agent._actor_optimizer._optimizer.state and not agent._critic_optimizer._optimizer.state
    assert agent._actor_kl_limit==.02
    agent._init_train();agent.set_mode(AgentMode.TEST)
    obs,info=env.reset()
    assert int(env._recovery_random_start_rows.sum())==146
    model=engine._solver.mj_model;data=mujoco.MjData(model)
    names=engine.get_obj_body_names(0)
    bodies=[next(i for i in range(1,model.nbody) if model.body(i).name.endswith(n)) for n in names]
    errors=[]
    def verify(label, worlds):
        # Synchronize reset state into MJ's existing buffer without stepping.
        engine._sim_state.pre_step_update()
        engine._solver._update_mjc_data(engine._solver.mjw_data,engine._sim_model,engine._sim_state.raw_state)
        qs=engine._solver.mjw_data.qpos.numpy();vs=engine._solver.mjw_data.qvel.numpy()
        actual_pos=engine.get_body_pos(0).cpu().numpy()
        actual_vel=engine.get_body_vel(0).cpu().numpy();actual_ang=engine.get_body_ang_vel(0).cpu().numpy()
        for world in worlds:
            data.qpos[:]=qs[world];data.qvel[:]=vs[world];mujoco.mj_forward(model,data)
            linear=[];angular=[]
            for bid in bodies:
                jp,jr=np.zeros((3,model.nv)),np.zeros((3,model.nv))
                mujoco.mj_jacBodyCom(model,data,jp,jr,bid)
                linear.append(jp@data.qvel);angular.append(jr@data.qvel)
            e=dict(stage=label,world=world,position_m=float(np.max(np.abs(actual_pos[world]-data.xpos[bodies]))),
                linear_m_s=float(np.max(np.abs(actual_vel[world]-linear))),angular_rad_s=float(np.max(np.abs(actual_ang[world]-angular))))
            # Reset pose FK uses float32 exp-map approximation; record its
            # sub-mm differences, reject material coordinate errors instead.
            if max(e['linear_m_s'],e['angular_rad_s'])>5e-3 or e['position_m']>2e-3:raise ValueError(e)
            errors.append(e)
    worlds=[int(env._recovery_ids[0]),int(env._recovery_ids[1]),511]
    verify('reset',worlds)
    for tick in range(8):
        with torch.no_grad():action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
        assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
        if tick in (0,7):verify('step'+str(tick),worlds)
        obs,info=env.reset(torch.nonzero(done,as_tuple=False).flatten())
    untouched=engine.get_body_vel(0)[511].clone()
    obs,info=env.reset(torch.tensor(worlds[:2],device='cuda'))
    verify('partial_reset',worlds)
    torch.testing.assert_close(untouched,engine.get_body_vel(0)[511])
    agent._curr_obs,agent._curr_info=env.reset()
    updates=[]
    for i in range(12):
        started=time.perf_counter();result=agent._train_iter();torch.cuda.synchronize()
        metrics={k:float(v) for k,v in result.items() if k in ('policy_kl','actor_steps_accepted','actor_steps_rejected','actor_learning_rate','actor_full_rollback','mean_return','critic_loss')}
        metrics.update(update=i,seconds=time.perf_counter()-started);updates.append(metrics)
        assert all(torch.isfinite(p).all() for p in agent.parameters())
        assert metrics['policy_kl']<=.020001
        print(json.dumps(metrics),flush=True)
    if sum(r['actor_steps_accepted'] for r in updates)<5:raise RuntimeError('KL guard prevents meaningful learning; inspect before launch')
    report=dict(passed=True,receipt=receipt,velocity_checks=errors,updates=updates,
        steady_update_mean_seconds=float(np.mean([r['seconds'] for r in updates[3:]])),
        selected_actor_lr=agent._actor_optimizer._optimizer.param_groups[0]['lr'],
        discarded_updates=len(updates),engine=engine.native_profile_report)
    (ROOT/'adam-velocity-preflight.json').write_text(json.dumps(report,indent=2));print('PREFLIGHT PASSED',flush=True)


if __name__=='__main__':main()
