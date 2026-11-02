"""Disposable physics/PPO test of the actual one-hot and disabled motor path."""
import os,sys,json,time
import numpy as np
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
root=Path(__file__).resolve().parents[2]
out=root/'Saved/MimicKitSlowLoco';p=out/'package'
sys.path[:0]=[str(p/'pipeline'),str(root/'Saved/MimicKitUEFN/dependencies'),str(p/'MimicKit/mimickit')]
import torch,yaml,warp as wp
from slow_loco_env import SlowLocoEnv
from omni_policy import OmniPPOAgent
from util import mp_util
from learning.base_agent import AgentMode

def main():
    os.chdir(p/'MimicKit');torch.set_num_threads(2);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6752)
    cfg,ec,ac=[yaml.safe_load((out/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    started=time.time();env=SlowLocoEnv(cfg,ec,64,'cuda:0',False)
    agent=OmniPPOAgent(ac,env,'cuda:0');agent._curr_obs,agent._curr_info=agent._reset_envs();agent._init_train()
    assert env.get_obs_space().shape==(160,)
    active=env.active_motion_labels
    expected=[sum(active[i % len(active)]==name for i in range(64)) for name in env.motion_labels]
    assert torch.bincount(env._fixed_motion_ids,minlength=8).tolist()==expected
    mask=wp.to_torch(env._engine.transfer_contact.p.motor_enabled)
    assert int((mask==0).sum())==(expected[4]+expected[5])*7
    # Solver's actuator order must be precisely the policy DOF order.
    assert env._engine._uefn_motors.dof_ids.tolist()==list(range(6,40))
    def check():
        obs=env._compute_obs();ids=env._motion_ids
        torch.testing.assert_close(obs[:,146:154],torch.eye(8,device='cuda:0')[ids])
        torch.testing.assert_close(obs[:,154:158],env._motion_limbs[ids])
        subset=torch.arange(0,64,3,device='cuda:0')
        torch.testing.assert_close(obs[subset],env._compute_obs(subset))
        assert torch.isfinite(obs).all()
        torch.testing.assert_close(ids,env._fixed_motion_ids)
    for ids in (torch.arange(64,device='cuda:0'),torch.arange(0,64,2,device='cuda:0')):
        env.reset(ids);check()
    max_disabled=0.;max_enabled=0.
    for tick in range(90):
        # Large alternating commands deliberately request torque in disabled joints.
        actions=torch.ones((64,34),device='cuda:0')*(3 if tick%2 else -3)
        env.step(actions)
        expected_reward=torch.exp(-env.loss_terms.sum(-1))-env.failure_penalty*(env._done_buf==1)
        torch.testing.assert_close(env._reward_buf,expected_reward)
        torque=env._engine._dof_forces[0]
        max_disabled=max(max_disabled,float(torque[mask==0].abs().max()))
        max_enabled=max(max_enabled,float(torque[mask==1].abs().max()))
        assert max_disabled<1e-7 and torch.isfinite(torque).all()
        reset=(env._done_buf!=0).nonzero().flatten()
        if len(reset):env.reset(reset)
        check()
    env._engine.validate_transfer_solver()
    agent._curr_obs,agent._curr_info=agent._reset_envs();agent.eval();agent.set_mode(AgentMode.TRAIN)
    with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
    for value in agent._exp_buffer._buffers.values():assert torch.isfinite(value).all()
    agent._build_train_data()
    failures=agent._exp_buffer.get_data('done')==1
    assert failures.any()
    torch.testing.assert_close(agent._exp_buffer.get_data('tar_val')[failures],agent._exp_buffer.get_data('reward')[failures])
    if env.failure_penalty:
        assert bool((agent._exp_buffer.get_data('reward')[failures]<=-99.).all())
    update=agent._update_model()
    assert all(torch.isfinite(v).all() for v in agent.parameters())
    env._engine.validate_transfer_solver();check()
    from observe_many import MultiRecorder
    recorder=MultiRecorder(env,out,8);recorder.phase_agent=agent
    original=agent._rollout_test
    def record(n):
        recorder.start()
        try:return original(n)
        finally:recorder.enabled=False
    agent._rollout_test=record
    evaluation=agent.test_model(1)
    replay=recorder.finish(0,0,dict(worlds=64,training_action_noise_std=.05,rollout_action_noise_std=0.))
    assert len(replay['replay_rows'])==len(active)
    assert {r['motion_name'] for r in replay['replay_rows']}==set(active)
    from replay import convert
    converted=convert(out/'replay.npz',json.loads((out/'geometry.json').read_text()),'slow_loco_preflight')
    for row in converted['rows']:
        metadata=row['evaluation'];rule=metadata['target_deviation']
        expected=rule['radius_by_motion_m'][metadata['motion_name']]
        assert {point['body']:point['radius_m'] for point in rule['points']} == {
            body:radius for body,radius in expected.items() if radius is not None}
        if getattr(env,'world_pelvis_termination',False):
            target=np.asarray(metadata['frame_world_pelvis_target'])
            assert target.ndim==2 and target.shape[1]==3 and np.isfinite(target).all()
            assert next(p for p in rule['points'] if p['body']=='pelvis')['target_space'] in ('world_reference','rolling_world_reference','periodic_world_reference')
            assert next(p for p in rule['points'] if p['body']=='pelvis')['radius_m']==rule.get('world_pelvis',{}).get('base_radius_m',.54)

    (out/'replay.json').write_text(json.dumps(converted))
    report=dict(passed=True,worlds=64,observations=160,onehot_and_flags_exact=True,reset_subset_exact=True,
        large_alternating_commands_ticks=90,disabled_torque_max_nm=max_disabled,enabled_torque_max_nm=max_enabled,
        disposable_ppo_update=True,phase_mse=float(update['phase_prediction_mse']),elapsed_seconds=time.time()-started,
        policy_clips=env.motion_labels,loss_names=env.loss_term_names,metadata=env.replay_loss_metadata(),
        replay_rows=len(active),replay_conversion_passed=True,evaluation=evaluation)
    (out/'preflight.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
