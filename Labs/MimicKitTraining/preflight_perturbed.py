"""Bounded contracts and real-engine smoke; never launches a trainer."""
import argparse
import io
import json
import os
from pathlib import Path
import sys
import time
import zipfile

LOCAL_ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser();parser.add_argument('--cpu', action='store_true');parser.add_argument('--baseline',action='store_true');args = parser.parse_args()
    root = LOCAL_ROOT/'Saved/MimicKitEquipment/perturbed-preparation/source' if args.cpu else Path('/workspace/mimickit_trial')
    vendor = LOCAL_ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit' if args.cpu else root/'MimicKit/mimickit'
    sys.path[:0] = [str(vendor)]
    if args.cpu:sys.path.insert(0, str(LOCAL_ROOT/'Saved/MimicKitUEFN/dependencies'))
    os.environ['PYGLET_HEADLESS'] = 'true'
    import numpy as np
    import torch
    import warp as wp
    import yaml
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from recovery_omni import RecoveryOmniEnv
    from util import mp_util, torch_util as q
    from envs.base_env import DoneFlags, EnvMode
    from learning.base_agent import AgentMode
    from perturbed_motion import com2_velocity
    from resume import restore
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    device = 'cpu' if args.cpu else 'cuda:0'
    wp.init();wp.set_device(device);mp_util.init(0, 1, device, 6794)
    cfg, ec, ac = [yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    checkpoint = LOCAL_ROOT/'Exports/MimicKitEquipment/20261019_stopped_47039/checkpoint_0047039_final.zip' if args.cpu else root/'resume.zip'
    if args.cpu:
        from audit_getup_strength import CpuEngine
        import omni_walk
        original = omni_walk.row_motion_weights
        omni_walk.row_motion_weights = lambda g,w,f,n: (1,original(g,w,f,2)[1])
        class Environment(PerturbedOmniEnv):
            def _build_engine(self, config, *a, **kw):return CpuEngine(config,*a,**kw)
        worlds = 1
    else:
        Environment = PerturbedOmniEnv
        worlds = 512
    if args.baseline:
        assert not args.cpu
        with zipfile.ZipFile(checkpoint) as saved:
            cfg=yaml.safe_load(saved.read('env_config.yaml'))
        Environment=RecoveryOmniEnv
    env = Environment(cfg, ec, worlds, device, False)
    agent = OmniPPOAgent(ac, env, device)
    restored = restore(agent, checkpoint)
    assert restored['prior_samples'] == 770703360 and restored['optimizer_restored']
    if args.baseline:
        agent._init_train();agent._curr_obs,agent._curr_info=agent._reset_envs()
        times=[]
        for i in range(6):
            begun=time.perf_counter();agent._train_iter();torch.cuda.synchronize();times.append(time.perf_counter()-begun)
        report=dict(passed=True,worlds=worlds,ppo_seconds=times,
                    transitions_per_second=512*agent._steps_per_iter/float(np.mean(times[2:])),
                    configuration='exact checkpoint47039 environment; no new perturbation or AE')
        (root/'baseline-preflight.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
        return
    agent.eval();agent.set_mode(AgentMode.TEST);env.set_mode(EnvMode.TEST)
    engine=env._engine;char=env._get_char_id()
    report = dict(restored=restored,worlds=worlds,normal=int((~env._perturbed_rows).sum()),
        perturbed=int(env._perturbed_rows.sum()),idle=env._idle_rows,
        perturbed_idle=int((env._perturbed_rows & (env._gaits[env._fixed_motion_ids]==-1)).sum()),
        perturbed_getup=int(env._perturbed_getup.sum()),min_speed_ratio=env._perturb_cfg['min_speed_ratio'])
    assert report['min_speed_ratio']==.7
    if not args.cpu:
        assert (report['normal'],report['perturbed'],report['idle'],report['perturbed_idle'])==(154,358,154,108)
        assert agent._obs_norm._mean.numel()==154
    obs,info=env.reset()
    if not torch.isfinite(obs).all():raise FloatingPointError('Invalid initial observations')
    if not args.cpu:
        report['max_start_com2_preservation_error_m_s']=float(env._initial_com2_error.max())
        if report['max_start_com2_preservation_error_m_s']>1e-4:
            raise ValueError('Reset failed to preserve physical COM2 velocity: '+str(report))
    # Perturbed get-ups use unmodified root pose and a pose from the loco pool.
    ids=torch.where(env._perturbed_getup)[0]
    torch.testing.assert_close(engine.get_root_pos(char)[ids],env._ref_root_pos[ids])
    torch.testing.assert_close(engine.get_root_rot(char)[ids],env._ref_root_rot[ids])
    assert (env._random_pose_frame[ids]>=0).all()
    torch.testing.assert_close(engine.get_dof_vel(char)[ids],env._ref_dof_vel[ids])
    # Height reset is a TIME truncation, regardless of old sphere/contact errors.
    if len(ids):
        world=ids[:1];saved=engine.get_body_pos(char)[world,env._head_id,2].clone()
        engine.get_body_pos(char)[world,env._head_id,2]=env._head_reset_height[env._motion_ids[world]]+.01
        env._time_buf[world]=1/30;env._update_done()
        assert int(env._done_buf[world][0])==DoneFlags.TIME.value
        engine.get_body_pos(char)[world,env._head_id,2]=saved
        obs,info=env.reset()
    # Normal rows must compute exactly the same weighted terms as before.
    normal=~env._perturbed_rows
    phases=[];samples=[];start=time.perf_counter();steps=24 if args.cpu else 180
    failures=0;head_resets=0
    for tick in range(steps):
        with torch.no_grad():
            action,_=agent._decide_action(obs,info)
            expected_phase=env._pending_phase.clone()
            obs,reward,done,info=env.step(action)
        if not torch.isfinite(obs).all() or not torch.isfinite(reward).all():
            raise FloatingPointError('Nonfinite physical rollout at tick '+str(tick))
        torch.testing.assert_close(reward,1/(1+env.loss_terms.sum(-1)))
        torch.testing.assert_close(obs[env._perturbed_rows,-2:],expected_phase[env._perturbed_rows])
        assert (env.loss_terms[env._perturbed_getup,:-1]==0).all()
        assert (env.loss_terms[normal,-1]==0).all()
        if tick in (0,8,23,80,139,179):
            pos=engine.get_body_pos(char);rot=engine.get_body_rot(char);angular=engine.get_body_ang_vel(char)
            velocity=engine.get_body_vel(char)-torch.cross(angular,q.quat_rotate(rot,env._body_com),dim=-1)
            baseline=RecoveryOmniEnv._tracking_losses(env,pos,rot,velocity,angular,env.reward_target_vel,env.reward_target_ang)
            torch.testing.assert_close(env.loss_terms[normal,:-1],baseline[normal])
            samples.append(dict(tick=tick+1,mean_reward=float(reward.mean()),max_cost=float(env.loss_terms.sum(-1).max())))
        failures+=int(((done==1)&env._perturbed_rows).sum())
        head_resets+=int((env._reset_reason==2).sum())
        reset=torch.where(done!=0)[0]
        obs,info=env.reset(reset)
        if len(reset):assert (env._prior.valid[env._prior_index[reset[env._perturbed_rows[reset]]]]==1).all()
    if not args.cpu:torch.cuda.synchronize()
    elapsed=time.perf_counter()-start
    report.update(passed=True,rollout_ticks=steps,rollout_seconds=elapsed,samples=samples,
        perturbed_failures=failures,head_height_resets=head_resets,phase_feedback_verified=True,
        normal_loss_equivalence=True,getup_body_mse_zero=True)
    if not args.cpu:
        agent._init_train()
        agent._curr_obs, agent._curr_info = agent._reset_envs()
        from health import install_guard
        install_guard(agent,lambda detail:print('PREFLIGHT ERROR '+json.dumps(detail),flush=True))
        times=[]
        for i in range(5):
            begun=time.perf_counter();result=agent._train_iter();torch.cuda.synchronize();times.append(time.perf_counter()-begun)
            if not all(torch.isfinite(p).all() for p in agent.parameters()):raise FloatingPointError('PPO produced invalid weights')
        report.update(discarded_ppo_updates=5,ppo_seconds=times,transitions_per_second=512*agent._steps_per_iter/float(np.mean(times[1:])))
    destination=(LOCAL_ROOT/'Saved/MimicKitEquipment/perturbed-preparation/cpu_preflight.json') if args.cpu else root/'perturbed-preflight.json'
    destination.write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
