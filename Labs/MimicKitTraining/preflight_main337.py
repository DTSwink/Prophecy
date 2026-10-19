"""Bounded real-engine GPU smoke before resuming the user's checkpoint."""
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
    env=RecoveryOmniEnv(cfg,ec,512,'cuda:0',False)
    engine=env._engine;assert not hasattr(engine,'transfer_contact')
    assert not getattr(engine._solver.mjw_model,'uefn_compound_limits',None)
    agent=OmniPPOAgent(ac,env,'cuda:0');receipt=restore(agent,ROOT/'resume.zip')
    assert agent._critic_optimizer._grad_clip==10.
    assert agent._actor_optimizer._grad_clip==0.
    for optimizer in (agent._critic_optimizer,agent._actor_optimizer):
        assert all(group['lr']==1e-4 for group in optimizer._optimizer.param_groups)
    agent._init_train();agent.set_mode(AgentMode.TEST)
    obs,info=env.reset();assert bool((env._recovery_start_frame[env._recovery_rows]==0).all())
    assert receipt['prior_samples']==337739776
    assert len(env._recovery_ids)==round(env._idle_rows*.95)
    assert env._recovery_target_radius_m==.30 and env.target_radius_m==.27
    assert env._recovery_pelvis_velocity_multiplier==2.
    assert 'termination_remaining' not in env.loss_term_names
    assert env._reset_after_getup and env._recovery_sphere_only and not env._absolute_recovery
    m=engine._solver.mj_model;d=mujoco.MjData(m)
    names=engine.get_obj_body_names(0)
    ids=[next(i for i in range(1,m.nbody) if m.body(i).name.endswith(name)) for name in names]
    peak=0.;episodes=0;extra_peak=0.
    for tick in range(24):
        with torch.no_grad():action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
        assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
        torch.testing.assert_close(reward,1/(1+env.loss_terms.sum(-1)))
        from util import torch_util as q
        ang=engine.get_body_ang_vel(0)
        vel=engine.get_body_vel(0)-torch.cross(ang,q.quat_rotate(engine.get_body_rot(0),env._body_com),dim=-1)
        expected=(vel[:,0]-env.reward_target_vel[:,0]).square().mean(-1)*env.loss_weights['linear_velocity_mse']/len(names)*env._recovery_rows
        torch.testing.assert_close(env.loss_terms[:,-1],expected)
        extra_peak=max(extra_peak,float(expected.max()))
        assert bool((env.loss_terms[~env._recovery_rows,-1]==0).all())
        if tick in (0,7,23):
            d.qpos[:]=engine._solver.mjw_data.qpos.numpy()[0]
            mujoco.mj_kinematics(m,d)
            actual=engine.get_body_pos(0)[0].cpu().numpy()
            error=float(abs(actual-d.xpos[ids]).max());peak=max(peak,error)
            if error>2e-5:raise ValueError('Native/Newton body coordinate mismatch '+str(error))
        reset=torch.nonzero(done,as_tuple=False).flatten();episodes+=len(reset)
        obs,info=env.reset(reset)
    # Five real PPO updates validate the approved critic cap and new curriculum.
    agent._curr_obs,agent._curr_info=env.reset()
    from health import install_guard
    def diagnostic(detail):
        (ROOT/'main337-diagnostic.json').write_text(json.dumps(detail,indent=2));print('DIAGNOSTIC '+json.dumps(detail),flush=True)
    install_guard(agent,diagnostic)
    optimization=[]
    for label,optimizer in [('actor',agent._actor_optimizer),('critic',agent._critic_optimizer)]:
        original=optimizer.step
        def checked(loss,original=original,label=label):
            if not bool(torch.isfinite(loss)):
                diagnostic(dict(stage=label,reason='nonfinite loss before optimizer',history=optimization[-6:]));raise FloatingPointError('Nonfinite '+label+' loss')
            value=float(loss)
            original(loss)
            bad=[name for name,p in agent.named_parameters() if not bool(torch.isfinite(p).all())]
            norm=agent._obs_norm.normalize(agent._exp_buffer._buffers['obs'])
            optimization.append(dict(stage=label,loss=value,normalized_observation_peak=float(norm.abs().max())))
            if bad:
                diagnostic(dict(stage=label,reason='nonfinite parameter after optimizer',parameters=bad,history=optimization[-6:]));raise FloatingPointError('Nonfinite '+label+' parameters')
        optimizer.step=checked
    started=time.perf_counter()
    results=[]
    for update in range(5):
        result=agent._train_iter();torch.cuda.synchronize()
        assert all(torch.isfinite(p).all() for p in agent.parameters())
        assert np.isfinite(result['mean_return'])
        results.append(dict(update=update,mean_return=float(result['mean_return'])))
    diagnostic(dict(passed=True,updates=results,optimization=optimization[-6:]))
    report=dict(passed=True,worlds=512,ticks=24,episodes=episodes,restored=receipt,pelvis_extra_peak=extra_peak,
                max_body_mapping_error_m=peak,smoke_update_seconds=time.perf_counter()-started,
                engine=engine.native_profile_report,torch_peak_memory_bytes=torch.cuda.max_memory_allocated(),
                discarded_optimizer_updates=5,critic_grad_clip=10.,actor_grad_clip=0.,learning_rate=1e-4)
    (ROOT/'main337-preflight.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
