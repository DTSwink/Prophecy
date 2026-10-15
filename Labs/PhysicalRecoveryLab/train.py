"""Local GPU get-up training. Run outputs stay under Saved/Robotics/runs."""
from pathlib import Path
import argparse
from dataclasses import asdict
import importlib.util
import json
import time
import torch
import warp as wp
from mjlab.rl.runner import MjlabOnPolicyRunner
from recovery_env import RecoveryEnv,OUT
from replay import ReplayWriter

def rescale_critic_units(algorithm,ratio):
    """Convert saved values with reward units; actor and its Adam state survive."""
    if ratio==1:return
    output=algorithm.critic.mlp[-1]
    if not isinstance(output,torch.nn.Linear) or output.out_features!=1:
        raise ValueError('Reward-unit migration expects a scalar linear critic output')
    with torch.no_grad():
        output.weight.mul_(ratio);output.bias.mul_(ratio)
    # Old Adam moments belong to the preceding loss units. Preserve the actor's.
    for parameter in algorithm.critic.parameters():algorithm.optimizer.state.pop(parameter,None)

class RecoveryRunner(MjlabOnPolicyRunner):
    transition_offset=0
    step_offset=0

    def load(self,path,*args,training_transitions=None,**kwargs):
        header=torch.load(path,map_location='cpu',weights_only=False)
        contract=header['infos']['physical_recovery']
        if contract['rig_sha256']!=self.env.cfg['rig_sha256'] or contract['controller']!=self.env.cfg['controller']:
            raise ValueError('Checkpoint rig/controller differs; start a named new experiment')
        if contract.get('previous_action_observation','applied')!=self.env.cfg.get('previous_action_observation','applied'):
            raise ValueError('Previous-action observation meaning changed; start a fresh policy')
        result=super().load(path,*args,**kwargs)
        ratio=self.env.cfg.get('reward_scale',1.)/contract.get('reward_scale',1.)
        if ratio!=1:
            rescale_critic_units(self.alg,ratio)
            print(f'Converted critic reward units by {ratio:.8g}; actor unchanged, critic optimizer moments reset.',flush=True)
        recorded=int(header['infos'].get('training_transitions',
            (header['iter']+1)*contract['num_envs']*self.cfg['num_steps_per_env']))
        if header['infos'].get('transition_counter_version',1)<2 and training_transitions is None:
            # The old save code added the resumed step count twice. Do not
            # guess a correction if historical batch sizes are unknown.
            direct=int(self.env.common_step_counter)*contract['num_envs']
            if recorded!=direct:
                raise ValueError('Legacy checkpoint has ambiguous cumulative count; supply audited --resume-transitions')
        self.transition_offset=int(training_transitions) if training_transitions is not None else recorded
        self.step_offset=int(self.env.common_step_counter)
        self.current_learning_iteration+=1
        self.logger.tot_timesteps=self.transition_offset
        return result

    def save(self,path,infos=None):
        transitions=self.transition_offset+(self.env.common_step_counter-self.step_offset)*self.env.num_envs
        super().save(path,{**(infos or {}),"physical_recovery":self.env.cfg,"training_transitions":transitions,
            'transition_counter_version':2,'run_start_policy_steps':self.step_offset,'resume_transition_offset':self.transition_offset})
        run=Path(path).parent
        count=self.env.history_count
        episode_frame=int(self.env.episode_length_buf[0].item())
        count=min(count,episode_frame or self.env.max_episode_length)
        end=self.env.common_step_counter%len(self.env.history)
        history=torch.roll(self.env.history,shifts=-end,dims=0)[-count:].cpu().numpy()
        import numpy as np
        np.savez_compressed(run/"latest-rollout.npz",qpos=history,policy_hz=30,iteration=self.current_learning_iteration)
        status={"iteration":self.current_learning_iteration,"policy_steps":self.env.common_step_counter,
                "training_transitions":transitions,"physics_world_steps":transitions*8,
                "checkpoint":str(Path(path).resolve()),"updated_unix":time.time(),
                "initial":self.env.initial,"kind":"physical_recovery_v1"}
        (run/"status.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
        if getattr(self,"replay",None):
            self.replay.publish(history,self.current_learning_iteration,path,
                {"training_transitions":transitions,"physics_world_steps":transitions*8,"num_envs":self.env.num_envs})
        if (run/'stop.request').exists():
            (run/'stop.request').unlink()
            raise TrainingStopped('Stopped after saving checkpoint at user/diagnostic request')


class TrainingStopped(Exception):pass

def main():
    p=argparse.ArgumentParser();p.add_argument("--worlds",type=int,default=256)
    p.add_argument("--iterations",type=int,default=100);p.add_argument("--run",default="fixed_prone_01")
    p.add_argument("--resume");p.add_argument("--initial",choices=("fixed","bank"),default="fixed")
    p.add_argument('--pose-bank',default='rig-passive.npz')
    p.add_argument('--resume-transitions',type=int,help='Audited correction for legacy checkpoint metadata only')
    p.add_argument("--live-replay",action="store_true")
    p.add_argument('--diagnose',action='store_true')
    p.add_argument('--native-motors',action='store_true')
    p.add_argument('--relative-targets',action='store_true')
    p.add_argument('--standing-fraction',type=float,default=0.)
    p.add_argument('--action-rate-sum',action='store_true',help='Use upstream summed action-change cost; legacy mean remains reproducible')
    p.add_argument('--reward-dt',action='store_true',help='Apply upstream reward-manager timestep scaling (1/30 at this policy rate)')
    p.add_argument('--raw-action-cost',action='store_true',help='Apply upstream action-rate cost to requested actions, before physical clipping')
    p.add_argument('--posture-profile',choices=('legacy','joint_scaled'),default='legacy')
    p.add_argument('--ccd-iterations',type=int,default=50)
    p.add_argument('--no-gyroscopic-forces',action='store_true',help='Match project Jolt rotational dynamics; requires full-rig validation')
    p.add_argument('--allow-speed-cap-mismatch',action='store_true',help='Exploratory learning only: record Jolt body-speed cap exceedances without clamping or stopping')
    args=p.parse_args()
    torch.set_num_threads(1); torch.set_num_interop_threads(1); wp.init()
    torch.manual_seed(42)
    for receipt in ("geometry-verification.json","phat-constraint-tests.json","limit-geometry.json","pd-tests.json","joint-calibration.json"):
        if not json.loads((OUT/receipt).read_text())["passed"]:
            raise RuntimeError(f"Required validation failed: {receipt}")
    run=OUT/"runs"/args.run;run.mkdir(parents=True,exist_ok=True)
    if not args.resume and any(run.glob('model_*.pt')):
        raise ValueError('Run already has checkpoints; explicitly resume or use a new run name')
    path=OUT/"vendor/mjlab_playground/src/mjlab_playground/getup/config/t1/rl_cfg.py"
    spec=importlib.util.spec_from_file_location("getup_reference_cfg",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    config=module.booster_t1_getup_ppo_runner_cfg()
    config.actor.hidden_dims=(256,128,128);config.critic.hidden_dims=(256,128,128)
    config.logger="tensorboard";config.upload_model=False;config.save_interval=25
    config.experiment_name="prophecy_physical_recovery";config.run_name=args.run
    cfg=asdict(config);cfg["check_for_nan"]=True
    env=RecoveryEnv(args.worlds,initial=args.initial,native_motors=args.native_motors,relative_targets=args.relative_targets,
                    integrator='implicitfast' if args.native_motors else 'euler',standing_fraction=args.standing_fraction,action_rate_sum=args.action_rate_sum,
                    ccd_iterations=args.ccd_iterations,gyroscopic_forces=not args.no_gyroscopic_forces,reward_dt_scale=args.reward_dt,pose_bank=args.pose_bank,raw_action_cost=args.raw_action_cost,posture_profile=args.posture_profile)
    if args.allow_speed_cap_mismatch and not args.diagnose:
        raise ValueError('Speed-cap exploration requires diagnostic monitoring')
    env.cfg['body_speed_cap_audit']='report_only' if args.allow_speed_cap_mismatch else 'stop'
    for name in ('geometry-verification.json','limit-geometry.json'):
        proof=json.loads((OUT/name).read_text())
        if any(proof.get(k)!=env.metadata[k] for k in ('rig_sha256','xml_sha256')):
            raise ValueError(f'Stale geometry validation: {name}')
    if args.standing_fraction:
        curriculum=json.loads((OUT/'curriculum-tests.json').read_text())
        if not curriculum['passed'] or curriculum['rig_sha256']!=env.metadata['rig_sha256']:
            raise ValueError('Standing practice and floor-metric separation have not passed for this rig')
    canonical=json.loads(json.dumps(env.controller.contract))
    if args.posture_profile!='legacy':
        proof=json.loads((OUT/'posture-reward-tests.json').read_text())
        if not proof['passed'] or proof['rig_sha256']!=env.metadata['rig_sha256'] or proof['contract']!=env.posture_reward.contract:
            raise ValueError('Posture reward has not passed independent pose/gate/legacy tests')
    if args.raw_action_cost:
        proof=json.loads((OUT/'raw-action-cost-tests.json').read_text())
        if not proof['passed'] or proof['rig_sha256']!=env.metadata['rig_sha256'] or not proof.get('requested_history_is_observed'):
            raise ValueError('Requested-action cost/history has not passed the saturation regression')
    if args.no_gyroscopic_forces:
        receipt=json.loads((OUT/'relative-native-no-gyro-tests.json').read_text())
        if not receipt['passed'] or receipt['controller']!=canonical or receipt['rig_sha256']!=env.metadata['rig_sha256'] or receipt['gyroscopic_forces'] or receipt['ccd_iterations']!=args.ccd_iterations:
            raise ValueError('Jolt gyroscopic setting has not passed full-rig tests')
        for name in ('failure1-no-gyro','failure2-no-gyro'):
            proof=json.loads((OUT/(name+'.json')).read_text())
            if not proof['passed'] or proof['rig_sha256']!=env.metadata['rig_sha256'] or proof['controller']!=canonical or proof['gyroscopic_forces']:
                raise ValueError(f'Matched dynamics have not passed {name}')
    if args.ccd_iterations!=50:
        prefix='relative-native' if args.relative_targets else 'native'
        receipt=json.loads((OUT/f'{prefix}-ccd{args.ccd_iterations}-tests.json').read_text())
        if not receipt['passed'] or receipt['controller']!=canonical or receipt['rig_sha256']!=env.metadata['rig_sha256'] or receipt['ccd_iterations']!=args.ccd_iterations:
            raise ValueError('Current contact iteration setting has not passed controller/stress tests')
    if args.resume and Path(args.resume).resolve().parent==run.resolve():
        old=torch.load(args.resume,map_location='cpu',weights_only=False)['infos']['physical_recovery']
        defaults={'integrator':'implicitfast','solver':'newton','ccd_iterations':50,'gyroscopic_forces':True,'standing_practice_fraction':0.,
                  'reward_action_rate_reduction':'mean','reward_action_rate_source':'applied','reward_scale':1.,'initial':'fixed','pose_bank':'rig-passive.npz',
                  'pose_bank_sha256':env.cfg['pose_bank_sha256'],
                  'posture_reward':{'profile':'legacy','upright_gravity_error_threshold':.1,'weight':.5}}
        changed=[k for k,v in defaults.items() if old.get(k,v)!=env.cfg.get(k,v)]
        if changed:raise ValueError(f'Use a new run name when changing task/physics settings: {changed}')
    if args.native_motors:
        optimized=json.loads((OUT/'motor-derivative-tests.json').read_text())
        if not optimized['passed'] or optimized['rig_sha256']!=env.metadata['rig_sha256']:
            raise ValueError('Native derivative specialization has not passed for this rig')
        receipts=('relative-native-tests','failure1-relative-native','failure2-relative-native') if args.relative_targets else ('native-motor-tests','failure1-native-motors','failure2-native-motors')
        for name in receipts:
            receipt=json.loads((OUT/(name+'.json')).read_text())
            if not receipt['passed'] or receipt['controller']!=canonical or receipt['rig_sha256']!=env.metadata['rig_sha256']:
                raise ValueError(f'Current native controller has not passed {name}')
    else:
        raise ValueError('Explicit controller is retained for diagnostics only after the second recorded instability; use --native-motors')
    (run/"config.json").write_text(json.dumps({"ppo":cfg,"environment":env.cfg},indent=2),encoding="utf-8")
    runner=RecoveryRunner(env,cfg,str(run),device="cuda:0")
    if args.diagnose:
        from collections import deque
        recent=deque(maxlen=12)
        supplemental=json.loads((OUT/'rig-provenance.json').read_text())
        if supplemental.get('supplements_rig_sha256')!=env.metadata['rig_sha256']:
            raise ValueError('Velocity-cap provenance does not match the current rig')
        angular_limits=torch.full((env.sim.mj_model.nbody,),float('inf'),device=env.device)
        for body in supplemental['bodies']:
            angular_limits[env.sim.mj_model.body(body['name']).id]=body['max_angular_velocity_rad_s']
        body_velocity=wp.to_torch(env.sim.wp_data.cvel)
        cap_peak=0.;cap_world_ticks=0;cap_sampled_world_ticks=0
        step=env.step
        def checked_step(actions):
            nonlocal cap_peak,cap_world_ticks,cap_sampled_world_ticks
            import numpy as np
            before_q=env.qpos.clone();before_v=env.qvel.clone()
            recent.append((before_q,before_v,actions.clone()))
            result=step(actions)
            body_speed=body_velocity[:,:,:3].norm(dim=-1)
            speed_cap_exceeded=(body_speed>angular_limits[None,:]).any(1)
            if args.allow_speed_cap_mismatch:
                count=int(speed_cap_exceeded.sum());cap_world_ticks+=count;cap_sampled_world_ticks+=env.num_envs
                cap_peak=max(cap_peak,float(body_speed.max()))
                if count and cap_world_ticks==count:
                    print('Jolt angular-speed cap exceeded; continuing explicitly unmatched exploration. See speed-cap-audit.json.',flush=True)
                if count or env.common_step_counter%24==0:
                    (run/'speed-cap-audit.json').write_text(json.dumps({'sampled_world_ticks':cap_sampled_world_ticks,
                        'world_ticks_above_jolt_cap':cap_world_ticks,'peak_sampled_body_speed_rad_s':cap_peak,
                        'sampling':'once per policy tick, not all physics substeps','clamping_applied':False,
                        'transfer_parity_verified':False},indent=2),encoding='utf-8')
            obs=result[0]['actor'];good=torch.isfinite(obs).all(1)&(env.qvel.abs().amax(1)<500)
            if not args.allow_speed_cap_mismatch:good&=~speed_cap_exceeded
            if not good.all():
                bad=int(torch.nonzero(~good)[0,0])
                np.savez_compressed(run/'first-failure.npz',qpos=before_q[bad].cpu().numpy(),qvel=before_v[bad].cpu().numpy(),
                    actions=actions[bad].cpu().numpy(),next_qpos=env.qpos[bad].cpu().numpy(),next_qvel=env.qvel[bad].cpu().numpy(),
                    obs=obs[bad].cpu().numpy(),qacc=env.sim.wp_data.qacc.numpy()[bad],qM=env.sim.wp_data.qM.numpy()[bad],
                    qLD=env.sim.wp_data.qLD.numpy()[bad],D=env.sim.wp_data.efc.D.numpy()[bad],
                    nefc=env.sim.wp_data.nefc.numpy()[bad],J=env.sim.wp_data.efc.J.numpy()[bad],
                    sampled_body_angular_speed=body_speed[bad].cpu().numpy(),body_angular_limits=angular_limits.cpu().numpy())
                np.savez_compressed(run/'failure-prefix.npz',qpos=torch.stack([x[0][bad] for x in recent]).cpu().numpy(),
                    qvel=torch.stack([x[1][bad] for x in recent]).cpu().numpy(),actions=torch.stack([x[2][bad] for x in recent]).cpu().numpy())
                print(f'First failure: tick {env.common_step_counter} world {bad}; previous velocity {before_v[bad].abs().max().item()}; actions finite {torch.isfinite(actions).all().item()}',flush=True)
                raise RuntimeError('Diagnostic trigger: nonfinite state, generalized speed >500, or sampled body speed above original Jolt cap. Captured preceding12 policy ticks; no pose/velocity clamp applied.')
            return result
        env.step=checked_step
    if args.resume: runner.load(args.resume,training_transitions=args.resume_transitions)
    runner.replay=ReplayWriter(args.run) if args.live_replay else None
    # Check once at the boundary between completed PPO updates. A diagnostic
    # stop saves current weights immediately, rather than wasting up to another
    # save interval. No partial update or lost checkpoint is presented as saved.
    step_with_diagnostics=env.step
    def interruptible_step(actions):
        if env.common_step_counter and env.common_step_counter%cfg['num_steps_per_env']==0 and (run/'stop.request').exists():
            runner.save(str(run/f'model_{runner.current_learning_iteration}.pt'))
        return step_with_diagnostics(actions)
    env.step=interruptible_step
    try:
        runner.learn(args.iterations,init_at_random_ep_len=False)
    except TrainingStopped as stop:
        print(str(stop),flush=True)
    finally:
        if runner.replay: runner.replay.close()
    print("Training segment finished",flush=True)

if __name__=="__main__":main()
