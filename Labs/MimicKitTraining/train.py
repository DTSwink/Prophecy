"""MimicKit walking or finite-horizon height PPO, durable saves and bounded runtime."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import zipfile

os.environ.setdefault('PYGLET_HEADLESS','true')
os.environ.setdefault('WANDB_MODE','disabled')
os.environ.setdefault('OMP_NUM_THREADS','1')
ROOT=Path('/workspace/mimickit_trial')
REPO=ROOT/'MimicKit'
sys.path.insert(0,str(REPO/'mimickit'))
import torch
import numpy as np
import yaml
import pyglet
pyglet.options['headless']=True
import run as upstream
from observe import Recorder, TrainingRecorder
from backup import Backups
from resume import restore
from runtime_deadline import RuntimeDeadline

class StopRequested(Exception):
    pass

def atomic_json(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.replace(path)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worlds',type=int,default=4096)
    parser.add_argument('--control-mode',choices=['pos','vel','torque'],default='pos')
    parser.add_argument('--max-samples',type=int,default=None,help='Optional sample limit; otherwise the spending deadline controls duration')
    parser.add_argument('--name',default='humanoid_walk_01')
    parser.add_argument('--seconds',type=int,default=6600)
    parser.add_argument('--benchmark',action='store_true')
    parser.add_argument('--profile',action='store_true',help='Profile three updates after warmup, then remove instrumentation')
    parser.add_argument('--output-interval',type=int,default=100,help='PPO updates between evaluation, TensorBoard points and checkpoints')
    parser.add_argument('--action-noise',type=float,help='Fixed Gaussian standard deviation in normalized action units')
    parser.add_argument('--per-agent-noise',action='store_true',help='Sample a fixed sigma per world uniformly from zero to action-noise')
    parser.add_argument('--actor-lr',type=float,help='Override actor SGD learning rate; critic unchanged')
    parser.add_argument('--actor-grad-clip',type=float,help='Enable the upstream actor gradient norm cap')
    parser.add_argument('--evaluate',action='store_true',help='Opt in to separate deterministic test episodes')
    parser.add_argument('--continuous-loss',action='store_true',help='Neutral pose: average MSE across every episode step instead of the final frame')
    parser.add_argument('--best-loss',action='store_true',help='Neutral pose: terminal minimum MSE over the episode, including its starting pose')
    parser.add_argument('--timed-best-tail',action='store_true',help='Best-pose improvement with 4x-to-1x timing reward and five-frame pose/velocity tail')
    parser.add_argument('--tail-velocity-weight',type=float,default=1.0)
    parser.add_argument('--tail-multiplier',type=float,default=1.0)
    parser.add_argument('--include-pelvis-velocity',action='store_true')
    parser.add_argument('--amp-world-bodies',action='store_true',help='Standing AMP discriminator: heading-aligned world body pose/velocities; floor-only resets')
    parser.add_argument('--worst-body',action='store_true',help='World pose: use the body with largest position plus orientation MSE each tick')
    parser.add_argument('--height-band-calibration',type=Path,help='Verified fixed head/pelvis band weights from a prior checkpoint')
    parser.add_argument('--height-bands-only',action='store_true',help='Omit body pose MSE, keeping the calibrated head and pelvis height penalties')
    parser.add_argument('--feet-lateral-calibration',type=Path,help='Verified fixed pelvis-lateral foot separation threshold and weight')
    parser.add_argument('--feet-lateral-termination',action='store_true',help='Replace lateral foot loss with immediate failure above its threshold; no added failure cost')
    parser.add_argument('--valid-reset-pose-pool',action='store_true',help='Precompute noisy floor poses and sample only those within the spread limit')
    parser.add_argument('--termination-remaining-cost',action='store_true',help='Charge the failure tick loss for all remaining episode ticks')
    parser.add_argument('--feet-distance-multiple',type=float,help='Use full 3D foot distance, limited to this multiple of the standing target distance')
    parser.add_argument('--floor-impact-limit-n',type=float,help='Terminate above this normal floor-contact peak on any non-foot body, measured at physics substeps')
    parser.add_argument('--floor-impact-arms-head',action='store_true',help='Restrict floor impact detection to head and both upper arms, forearms and hands')
    parser.add_argument('--resume',type=Path)
    parser.add_argument('--resume-velocity-mse-scale',type=float,
        help='Allow prepared linear/angular velocity weights to differ from the checkpoint by this explicit factor')
    parser.add_argument('--resume-position-leeway',action='store_true',
        help='Explicitly adopt prepared position MSE allowances while retaining learned state')
    parser.add_argument('--task', choices=['walk', 'amp', 'amp_standing', 'head_height','neutral_pose','recovery_pose','world_pose'], default='walk')
    parser.add_argument('--absolute-walk',action='store_true',help='Four world-body motion errors; targets follow pelvis XY only')
    parser.add_argument('--absolute-loss-calibration',type=Path,help='Fixed initial four-term balance for absolute walking')
    parser.add_argument('--omni-run-lr',action='store_true',help='UEFN Run LR, 151 observations, 34 motors plus Phase E, 27cm termination')
    parser.add_argument('--zero-joint-armature',action='store_true',help='Explicit Run LR continuation with no added joint armature')
    parser.add_argument('--equipment-omni',type=Path,help='Prepared fresh 54-motion equipment experiment')
    parser.add_argument('--replay-rows',type=int,default=20,help='Equipment evaluation rows recorded without additional physics steps')
    a=parser.parse_args()
    if a.resume_velocity_mse_scale is not None:
        if not (a.resume and a.equipment_omni and math.isfinite(a.resume_velocity_mse_scale) and a.resume_velocity_mse_scale>0):
            parser.error('Velocity MSE rescale requires a resumed equipment run and a positive finite factor')
    if a.equipment_omni:
        a.omni_run_lr=True
        if not 1<=a.replay_rows<=a.worlds:parser.error('Replay rows must be between 1 and worlds')
    assert not a.omni_run_lr or (a.absolute_walk and a.control_mode=='vel' and a.worlds==512 and a.evaluate)
    assert not a.zero_joint_armature or (a.omni_run_lr and a.resume)
    assert not a.absolute_loss_calibration or a.absolute_walk
    assert not a.absolute_walk or a.task=='walk'
    assert a.control_mode=='pos' or a.task in ('walk','world_pose'), 'Velocity and torque control are supported for walking and world-pose tasks'
    assert not a.worst_body or a.task=='world_pose'
    assert not a.height_band_calibration or (a.task=='world_pose' and a.worst_body)
    assert not a.height_bands_only or a.height_band_calibration
    assert not a.feet_lateral_calibration or (a.height_band_calibration and not a.height_bands_only)
    assert not a.feet_lateral_termination or a.feet_lateral_calibration
    assert not a.valid_reset_pose_pool or a.feet_lateral_termination
    assert not a.termination_remaining_cost or a.feet_lateral_termination
    assert a.feet_distance_multiple is None or (a.feet_lateral_termination and math.isfinite(a.feet_distance_multiple) and a.feet_distance_multiple>0)
    assert a.floor_impact_limit_n is None or (a.termination_remaining_cost and math.isfinite(a.floor_impact_limit_n) and a.floor_impact_limit_n>0)
    assert not a.floor_impact_arms_head or a.floor_impact_limit_n is not None
    assert not a.amp_world_bodies or (a.task=='amp_standing' and not a.resume)
    assert not a.continuous_loss or a.task == 'neutral_pose'
    assert not a.best_loss or (a.task == 'neutral_pose' and not a.continuous_loss)
    assert not a.timed_best_tail or (a.task == 'neutral_pose' and not a.best_loss and not a.continuous_loss and not a.evaluate)
    assert math.isfinite(a.tail_velocity_weight) and a.tail_velocity_weight >= 0
    assert a.timed_best_tail or a.tail_velocity_weight == 1.0
    assert math.isfinite(a.tail_multiplier) and a.tail_multiplier >= 0
    assert a.timed_best_tail or (a.tail_multiplier == 1.0 and not a.include_pelvis_velocity)
    assert a.output_interval > 0
    assert a.action_noise is None or (math.isfinite(a.action_noise) and a.action_noise > 0)
    assert a.actor_lr is None or (math.isfinite(a.actor_lr) and a.actor_lr > 0)
    assert a.actor_grad_clip is None or (math.isfinite(a.actor_grad_clip) and a.actor_grad_clip > 0)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    os.chdir(REPO)
    directory=ROOT/'runs'/a.name
    directory.mkdir(parents=True,exist_ok=False)
    is_amp = a.task in ('amp','amp_standing')
    if is_amp:
        assert a.evaluate, 'AMP uses stock evaluation'
        assert not a.per_agent_noise and a.action_noise is None and a.actor_lr is None and a.actor_grad_clip is None
        config=yaml.safe_load((REPO/'data/envs/amp_humanoid_env.yaml').read_text())
        agent_file='data/agents/amp_humanoid_agent.yaml'
        if a.task=='amp_standing':
            target=json.loads(Path(__file__).with_name('amp_standing_target.json').read_text())
            config.update(episode_length=2.0,num_disc_obs_steps=3,init_pose=target['pose'],
                motion_file=str(Path(__file__).with_name('amp_standing_target.pkl')),
                reset_seed=20261014,reset_joint_noise_degrees=5.0,reset_floor_clearance_m=.002,
                upright_cohort_fraction=0. if a.amp_world_bodies else .2,early_termination_cohort='upright_only',
                discriminator_representation='heading_aligned_world_bodies' if a.amp_world_bodies else 'stock')
    elif a.task=='world_pose':
        target=json.loads(Path(__file__).with_name('amp_standing_target.json').read_text())
        config=dict(env_name='world_pose',char_file='data/assets/humanoid/humanoid.xml',
            camera_mode='track',episode_length=2.,global_obs=True,root_height_obs=True,
            init_pose=target['pose'],target_pose=target['pose'],
            key_bodies=['head','right_hand','left_hand','right_foot','left_foot'],
            reset_seed=20261014,reset_joint_noise_degrees=5.,reset_floor_clearance_m=.002,
            objective=('mean_episode_max_body_position_plus_orientation_mse' if a.worst_body else 'mean_episode_world_position_mse_plus_world_orientation_matrix_mse'),
            worst_body=a.worst_body,
            position_weight=1.,orientation_weight=1.,target_alignment='current_root_xy_fixed_world_heading')
        agent_file='data/agents/deepmimic_humanoid_ppo_agent.yaml'
    elif a.task != 'walk':
        config=yaml.safe_load(Path(__file__).with_name(a.task+'_env.yaml').read_text())
        agent_file=str(Path(__file__).with_name('head_height_agent.yaml'))
    else:
        config=yaml.safe_load((REPO/'data/envs/deepmimic_humanoid_env.yaml').read_text())
        config['motion_file']='data/motions/humanoid/humanoid_walk.pkl'
        agent_file='data/agents/deepmimic_humanoid_ppo_agent.yaml'
    if a.absolute_walk:
        config['absolute_world_body_objective']='four_equal_mse_exp_reward_xy_position_only'
    if a.absolute_loss_calibration:
        calibration=json.loads(a.absolute_loss_calibration.read_text())
        if a.omni_run_lr:
            assert calibration['initialization']=='fresh_uefn_runLR_seed20261014'
        else:
            assert a.resume, 'Calibrated walking must use its recorded initialization or continuation'
            with zipfile.ZipFile(a.resume) as bundle:
                prior=yaml.safe_load(bundle.read('env_config.yaml')).get('absolute_loss_calibration')
            if prior is None:
                assert hashlib.sha256(a.resume.read_bytes()).hexdigest()==calibration['checkpoint']['sha256']
            else:
                assert prior==calibration
        config['absolute_loss_calibration']=calibration
    if a.continuous_loss:
        config['continuous_reward']=True
        config['objective']='negative_mean_per_frame_body_position_error_m2'
    if a.best_loss:
        config['best_reward']=True
        config['objective']='negative_minimum_episode_body_position_error_m2_including_start'
    if a.timed_best_tail:
        config.update(best_reward=True, timed_best_tail=True, episode_length=50/30,
            objective='timed_best_improvement_plus_mean_tail_pose_and_joint_velocity',
            early_multiplier=4.0, tail_frames=5, tail_pose_weight=1.0, tail_velocity_weight=a.tail_velocity_weight)
        if a.tail_multiplier != 1.0: config['tail_multiplier']=a.tail_multiplier
        if a.include_pelvis_velocity: config['include_pelvis_velocity']=True
    if a.height_band_calibration:
        calibration=json.loads(a.height_band_calibration.read_text())
        assert calibration['validated'] and calibration['target_pose']==config['target_pose']
        config.update(height_band_weights=calibration['weights'],height_band_calibration=calibration,
            objective='mean_episode_worst_body_pose_plus_fixed_weight_head_and_pelvis_height_bands')
        if a.height_bands_only:
            config.update(height_bands_only=True,objective='mean_episode_fixed_weight_head_and_pelvis_height_bands_only')
    if a.feet_lateral_calibration:
        feet=json.loads(a.feet_lateral_calibration.read_text())
        assert feet['validated'] and feet['target_pose']==config['target_pose']
        if a.resume:
            with zipfile.ZipFile(a.resume) as bundle:
                previous_feet=yaml.safe_load(bundle.read('env_config.yaml')).get('feet_lateral_calibration')
            if previous_feet is None:
                assert hashlib.sha256(a.resume.read_bytes()).hexdigest()==feet['checkpoint']['sha256']
            else:
                assert previous_feet==feet, 'Keep the original fixed calibration when resuming'
        config['feet_lateral_calibration']=feet
        if a.feet_lateral_termination:
            config['feet_lateral_termination']=True
        if a.valid_reset_pose_pool:
            config['valid_reset_pose_pool']=True
        if a.termination_remaining_cost:
            config['termination_remaining_cost']=True
        if a.feet_distance_multiple is not None:
            config['feet_distance_multiple']=a.feet_distance_multiple
        if a.floor_impact_limit_n is not None:
            config['floor_impact_limit_n']=a.floor_impact_limit_n
            if a.floor_impact_arms_head:
                config['floor_impact_bodies']=['head','right_upper_arm','right_lower_arm','right_hand','left_upper_arm','left_lower_arm','left_hand']
    config_file=directory/'walking_env.yaml'
    config_file.write_text(yaml.safe_dump(config,sort_keys=False))
    agent_config=yaml.safe_load(Path(agent_file).read_text())
    if a.omni_run_lr:
        from omni_config import configure
        configure(config,{},agent_config,ROOT)
        config_file.write_text(yaml.safe_dump(config,sort_keys=False))
    if a.task in ('amp_standing','world_pose'):
        from networks import register_network
        register_network()
        agent_config['model'].update(actor_net='fc_1024_1024',critic_net='fc_1024_1024')
    agent_config['iters_per_output']=a.output_interval
    agent_config['iters_per_log']=min(10,a.output_interval)
    if a.resume:
        with zipfile.ZipFile(a.resume) as bundle:
            saved_agent_config=yaml.safe_load(bundle.read('agent_config.yaml'))
        agent_config['iters_per_log']=saved_agent_config.get('iters_per_log',saved_agent_config['iters_per_output'])
    if a.actor_lr is not None:agent_config['actor_optimizer']['learning_rate']=a.actor_lr
    if a.actor_grad_clip is not None:agent_config['actor_optimizer']['grad_clip']=a.actor_grad_clip
    if not a.evaluate:agent_config['test_episodes']=0
    if a.action_noise is not None:
        assert agent_config['model']['actor_std_type']=='FIXED'
        agent_config['model']['action_std']=a.action_noise
    if a.per_agent_noise:
        agent_config['per_agent_noise_seed']=20261014
        agent_config['per_agent_noise_distribution']='uniform_zero_to_action_std_fixed_per_world'
    agent_file=str(directory/'selected_agent.yaml')
    Path(agent_file).write_text(yaml.safe_dump(agent_config,sort_keys=False))
    engine_file='data/engines/newton_engine.yaml'
    if a.control_mode!='pos' or a.floor_impact_limit_n is not None:
        engine_config=yaml.safe_load(Path(engine_file).read_text())
        engine_config['control_mode']=a.control_mode
        if a.omni_run_lr:
            configure(config,engine_config,agent_config,ROOT)
            if a.zero_joint_armature:engine_config['uefn_zero_joint_armature']=True
        if a.floor_impact_limit_n is not None:
            engine_config['track_ground_contact_peaks']=True
        engine_file=str(directory/'selected_engine.yaml')
        Path(engine_file).write_text(yaml.safe_dump(engine_config,sort_keys=False))
    if a.equipment_omni:
        config=yaml.safe_load((a.equipment_omni/'env_config.yaml').read_text())
        engine_config=yaml.safe_load((a.equipment_omni/'engine_config.yaml').read_text())
        agent_config=yaml.safe_load((a.equipment_omni/'agent_config.yaml').read_text())
        if a.actor_lr is not None:agent_config['actor_optimizer']['learning_rate']=a.actor_lr
        agent_config.update(iters_per_output=a.output_interval,iters_per_log=min(10,a.output_interval))
        assert config['equipment_conditioning'] and not config['arm_injuries_enabled']
        assert 0 < config['idle_row_fraction'] <= 1 and agent_config['model']['auto_phase_unit_output']
        config_file.write_text(yaml.safe_dump(config,sort_keys=False))
        Path(engine_file).write_text(yaml.safe_dump(engine_config,sort_keys=False))
        Path(agent_file).write_text(yaml.safe_dump(agent_config,sort_keys=False))
    args=upstream.load_args(['train', '--env_config',str(config_file),
        '--engine_config',engine_file,
        '--agent_config',agent_file,
        '--rand_seed','20261014','--visualize','false','--logger','tb'])
    upstream.mp_util.init(0,1,'cuda:0',6741)
    upstream.set_rand_seed(args)
    upstream.set_np_formatting()
    if a.omni_run_lr:
        from omni_walk import OmniWalkEnv
        if config.get('idle_recovery'):
            from recovery_omni import RecoveryOmniEnv as OmniWalkEnv
        env=OmniWalkEnv(config,yaml.safe_load(Path(engine_file).read_text()),a.worlds,'cuda:0',False)
    elif a.absolute_walk:
        from absolute_walk import AbsoluteWalkEnv
        env=AbsoluteWalkEnv(config,yaml.safe_load(Path(engine_file).read_text()),a.worlds,'cuda:0',False)
    elif a.task == 'amp_standing':
        from amp_standing import StandingAMPEnv
        engine_config=yaml.safe_load((REPO/'data/engines/newton_engine.yaml').read_text())
        if a.amp_world_bodies:
            from amp_world_bodies import WorldBodyStandingAMPEnv
            StandingAMPEnv=WorldBodyStandingAMPEnv
        env=StandingAMPEnv(config,engine_config,a.worlds,'cuda:0',False)
    elif a.task=='world_pose':
        from world_pose import WorldPoseEnv
        engine_config=yaml.safe_load(Path(engine_file).read_text())
        env=WorldPoseEnv(config,engine_config,a.worlds,'cuda:0',False)
    elif a.task == 'head_height':
        from head_height import HeadHeightEnv
        engine_config=yaml.safe_load((REPO/'data/engines/newton_engine.yaml').read_text())
        env=HeadHeightEnv(config,engine_config,a.worlds,'cuda:0',False)
    elif a.task=='neutral_pose':
        from neutral_pose import NeutralPoseEnv
        if a.timed_best_tail:
            from timed_pose import TimedNeutralPoseEnv
            NeutralPoseEnv = TimedNeutralPoseEnv
        engine_config=yaml.safe_load((REPO/'data/engines/newton_engine.yaml').read_text())
        env=NeutralPoseEnv(config,engine_config,a.worlds,'cuda:0',False)
    elif a.task=='recovery_pose':
        from recovery_pose import RecoveryPoseEnv
        engine_config=yaml.safe_load((REPO/'data/engines/newton_engine.yaml').read_text())
        env=RecoveryPoseEnv(config,engine_config,a.worlds,'cuda:0',False)
    else:
        env=upstream.build_env(args,a.worlds,'cuda:0',False)
    if a.omni_run_lr:
        from omni_policy import OmniPPOAgent
        agent=OmniPPOAgent(agent_config,env,'cuda:0')
    elif a.per_agent_noise:
        from agent_noise import PerAgentNoisePPO
        agent=PerAgentNoisePPO(agent_config,env,'cuda:0')
    else:
        agent=upstream.build_agent(args,env,'cuda:0')
    upstream.save_config_files(args,str(directory))
    add_height_records=False
    if a.resume:
        with zipfile.ZipFile(a.resume) as bundle:
            for name in ['engine_config.yaml','env_config.yaml','agent_config.yaml']:
                old=yaml.safe_load(bundle.read(name))
                new=yaml.safe_load((directory/name).read_text())
                if a.omni_run_lr:
                    if name=='env_config.yaml' and a.resume_position_leeway:
                        assert a.equipment_omni and new.get('position_mse_leeway')
                        old['position_mse_leeway']=new['position_mse_leeway']
                    if name=='env_config.yaml' and a.resume_velocity_mse_scale is not None:
                        # Explicit objective-only continuation. Other weights and
                        # calibration evidence must still match the saved run.
                        weights=old['absolute_loss_calibration']['weights']
                        for term in ('linear_velocity_mse','angular_velocity_mse'):
                            weights[term] *= a.resume_velocity_mse_scale
                    if name=='agent_config.yaml' and new.get('actor_kl_limit',0)>0:
                        # October19 approved Adam migration and transactional KL guard.
                        for key in ('actor_optimizer','critic_optimizer','actor_kl_limit','actor_kl_probe_size','actor_min_learning_rate'):
                            old[key]=new[key]
                    if (name=='agent_config.yaml' and a.equipment_omni
                            and config.get('idle_recovery',{}).get('pelvis_linear_velocity_multiplier')==2.
                            and new.get('critic_optimizer',{}).get('grad_clip')==10.):
                        # Authorized main337 critic stabilization; retain actor,
                        # learning rates, optimizer state and every other setting.
                        old['critic_optimizer']['grad_clip']=10.
                    if name=='engine_config.yaml' and new.get('transfer_floor_aware_projection'):
                        # User-authorized floor-feasible position projection.
                        old['transfer_floor_aware_projection']=True
                    if name=='env_config.yaml' and new.get('idle_recovery'):
                        # Explicit recovery curriculum resume; learned tensors,
                        # optimizer and all remaining settings stay unchanged.
                        old['idle_recovery']=new['idle_recovery']
                        if new['idle_recovery'].get('sphere_only') and new.get('target_radius_m')==.30:
                            # User-requested recovery sphere radius change on resume.
                            old['target_radius_m']=new['target_radius_m']
                        # Explicitly authorized idle cohort change; preserve all
                        # learned state while constructing new physical episodes.
                        old['idle_row_fraction']=new['idle_row_fraction']
                        if new.get('tracking_reward_form')=='reciprocal_sum':
                            old['tracking_reward_form']='reciprocal_sum'
                        assert 'adaptive_motion_rows' not in new
                        old.pop('adaptive_motion_rows',None)
                    if name=='engine_config.yaml' and 'uefn_motor_torque_caps_nm' in new:
                        # Explicit motor-only resume; the engine validates named increases.
                        old['uefn_motor_torque_caps_nm']=new['uefn_motor_torque_caps_nm']
                    if name=='env_config.yaml' and 'velocity_command_margin' in new:
                        # User-approved command envelope; keep every other setting.
                        assert new['velocity_command_margin']==.05
                        old.setdefault('velocity_command_margin', .05)
                    if name=='env_config.yaml' and a.equipment_omni and 'adaptive_motion_rows' in new:
                        # Authorized minute-based row allocation; all other config must match.
                        old.setdefault('adaptive_motion_rows', new['adaptive_motion_rows'])
                    # The user-approved end-step bounded motor solve applies
                    # to resumed checkpoints too. Save it explicitly in the new
                    # config; never rewrite the historical checkpoint archive.
                    if name=='engine_config.yaml':
                        if new.get('uefn_native_profile'):
                            assert new['uefn_native_profile']=='native_runlr_soft_contact_20261018'
                            for key in ('uefn_native_profile','uefn_bounded_velocity_motors','uefn_jolt_contact_profile','transfer_floor_aware_projection'):
                                old[key]=new[key]
                        else:
                            assert new['uefn_bounded_velocity_motors'] is True
                            old['uefn_bounded_velocity_motors']=True
                            assert new['uefn_jolt_contact_profile'] is True
                            old['uefn_jolt_contact_profile']=True
                        assert new['uefn_zero_joint_armature'] is True
                        old['uefn_zero_joint_armature']=True
                    if name=='engine_config.yaml' and a.zero_joint_armature:
                        old['uefn_zero_joint_armature']=True
                    assert old==new,f'Run LR resume config mismatch: {name}'
                    continue
                if name=='env_config.yaml' and a.absolute_walk:
                    old['absolute_world_body_objective']=new['absolute_world_body_objective']
                    if a.absolute_loss_calibration:old['absolute_loss_calibration']=new['absolute_loss_calibration']
                if name=='env_config.yaml' and a.task=='head_height' and old.get('objective')=='episode_maximum_of_head_plus_pelvis_height' and new.get('objective')=='minimum_of_independent_head_and_pelvis_episode_maxima':
                    old['objective']=new['objective']
                    add_height_records=True
                if name=='env_config.yaml' and a.timed_best_tail:
                    assert old.get('best_reward') is True
                    assert old.get('objective') in ('negative_minimum_episode_body_position_error_m2_including_start', new['objective'])
                    for key in ('timed_best_tail','episode_length','objective','early_multiplier','tail_frames','tail_pose_weight','tail_velocity_weight'):
                        old[key]=new[key]
                    for key in ('tail_multiplier','include_pelvis_velocity'):
                        if key in new: old[key]=new[key]
                if name=='env_config.yaml' and a.feet_lateral_calibration and 'feet_lateral_calibration' not in old:
                    # Explicitly authorized addition; all pre-existing settings must match.
                    old['feet_lateral_calibration']=new['feet_lateral_calibration']
                if name=='env_config.yaml' and a.feet_lateral_termination:
                    assert old.get('feet_lateral_calibration')==new['feet_lateral_calibration']
                    old['feet_lateral_termination']=True
                if name=='env_config.yaml' and a.valid_reset_pose_pool:
                    old['valid_reset_pose_pool']=True
                if name=='env_config.yaml' and a.termination_remaining_cost:
                    old['termination_remaining_cost']=True
                if name=='env_config.yaml' and a.feet_distance_multiple is not None:
                    old['feet_distance_multiple']=a.feet_distance_multiple
                if name=='env_config.yaml' and a.floor_impact_limit_n is not None:
                    old['floor_impact_limit_n']=a.floor_impact_limit_n
                    if a.floor_impact_arms_head:old['floor_impact_bodies']=new['floor_impact_bodies']
                if name=='engine_config.yaml' and a.floor_impact_limit_n is not None:
                    old['track_ground_contact_peaks']=True
                if name=='agent_config.yaml':old['test_episodes']=new['test_episodes']
                assert old==new,f'Resume config mismatch: {name}'
    resumed=restore(agent,a.resume,add_height_records=add_height_records) if a.resume else dict(prior_samples=0,iteration_offset=0)
    if a.resume_position_leeway:
        resumed['position_mse_leeway']=dict(config['position_mse_leeway'])
    if a.resume_velocity_mse_scale is not None:
        resumed['velocity_mse_rescale']=dict(factor=a.resume_velocity_mse_scale,
            terms=['linear_velocity_mse','angular_velocity_mse'],rows='all',
            weights=dict(config['absolute_loss_calibration']['weights']))
    if a.resume and a.actor_lr is not None:
        # load_state_dict restores the saved LR too; apply an explicit user
        # override afterwards without clearing the optimizer's accumulated state.
        from resume import override_actor_learning_rate
        resumed['actor_learning_rate_override']=override_actor_learning_rate(agent,a.actor_lr)
    iteration_offset=resumed['iteration_offset']
    if a.zero_joint_armature:resumed['joint_armature_removed']=True
    if hasattr(env,'velocity_command_report'):
        command_report=dict(env.velocity_command_report,
            action_scale=agent._a_norm.get_std().detach().cpu().tolist(),
            action_offset=agent._a_norm.get_mean().detach().cpu().tolist(),
            normalized_penalty_bound=agent._a_norm.normalize(env._action_bound_high).detach().cpu().tolist(),
            physical_noise_std=(agent._a_norm.get_std()*agent_config['model']['action_std']).detach().cpu().tolist())
        atomic_json(directory/'velocity_command_bounds.json',command_report)
    atomic_json(directory/'resume.json',resumed)
    if getattr(env,'_recovery_ready',False):
        assigned=env._gaits[env._fixed_motion_ids]
        atomic_json(directory/'recovery_setup.json',dict(
            worlds=a.worlds,recovery_rows=len(env._recovery_ids),
            recovery_random_start_rows=int(env._recovery_random_start_rows.sum()),
            recovery_frame_zero_rows=int((env._recovery_rows & ~env._recovery_random_start_rows).sum()),
            ordinary_idle_rows=env._idle_rows-len(env._recovery_ids),
            walking_rows=int((assigned==0).sum()),running_rows=int((assigned==1).sum()),
            adaptive_sampling=False,configuration=config['idle_recovery']))
    if hasattr(env._engine,'torque_envelope_report'):
        atomic_json(directory/'torque_envelope.json',env._engine.torque_envelope_report)
    if hasattr(env._engine,'native_profile_report'):
        atomic_json(directory/'native_physics.json',env._engine.native_profile_report)
    if a.valid_reset_pose_pool:
        atomic_json(directory/'reset_pose_pool.json',env.reset_pose_pool_report)
    noise_metadata=dict(training_action_noise_std=float(agent_config['model']['action_std']))
    rollout_sigma=noise_metadata['training_action_noise_std']
    if a.per_agent_noise:
        sigmas=agent.agent_action_logstd.exp().flatten().cpu().tolist()
        noise_metadata=dict(training_action_noise_std=None,training_action_noise_distribution='uniform_fixed_per_agent',
            training_action_noise_range=[0.,float(agent_config['model']['action_std'])],
            training_action_noise_actual_min=min(sigmas),training_action_noise_actual_max=max(sigmas))
        rollout_sigma=sigmas[0]
        atomic_json(directory/'agent_noise.json',dict(**noise_metadata,sigmas=sigmas))
    atomic_json(directory/'provenance.json',dict(upstream_commit='2ed1e6c093bb0829f55d33cb4f7a1731cfe6cb69',
        task=(config['absolute_world_body_objective'] if a.absolute_walk else (('AMP static standing target; 100% noisy floor; heading-aligned world body discriminator' if a.amp_world_bodies else 'AMP static standing target; fixed 20% upright / 80% noisy floor cohorts') if a.task=='amp_standing' else 'stock AMP humanoid spinkick' if a.task=='amp' else 'stock DeepMimic humanoid walking' if a.task=='walk' else config['objective'])),worlds=a.worlds,seed=20261014,
        **noise_metadata,evaluation_enabled=a.evaluate,
        wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        training_config_changed=(['world-body tracking; target alignment from config; reward='+config.get('tracking_reward_form','exp_negative_sum')] if a.absolute_walk else ['PPO without discriminator; same actor/critic optimizer settings','1024x1024 actor/critic; 140 inputs with world body orientations','100% noisy floor starts, 2-second timeout, fixed-heading world pose MSE throughout episode'] if a.task=='world_pose' else ['actor/critic 1024x1024; discriminator hidden layers unchanged',f'{a.worlds} worlds; static standing reference; three-frame discriminator',('100% noisy floor reset; actual reset history; heading-aligned all-body world states, 675 discriminator inputs' if a.amp_world_bodies else 'fixed upright cohort; upright-only early termination; noisy floor reset; actual reset history'),'two-second horizon; stock AMP rewards/optimizers/controller/physics'] if a.task=='amp_standing' else ['512 worlds; stock Newton backend; logging/checkpoint wrapper'] if a.task=='amp' else ['motion_file only'] if a.task=='walk' else ['reference-free CharEnv',('random 50/50 back/front joint-noisy floor reset' if a.task=='recovery_pose' else 'supine reset'),('50-step finite horizon:45 reach+5 tail' if a.timed_best_tail else '45-step finite horizon'),config['objective'],'action_bound_weight=0']),gpu=torch.cuda.get_device_name(0)))
    assert env._engine._graph is not None,'Expected vanilla Newton CUDA physics graph'
    record_training=not a.evaluate
    if a.task=='amp_standing':
        from observe import AMPTestCohortRecorder
        recorder=AMPTestCohortRecorder(env,directory,agent,lambda:agent._iter+iteration_offset)
    elif a.equipment_omni and a.replay_rows>1:
        from observe_many import MultiRecorder
        recorder=MultiRecorder(env,directory,a.replay_rows)
    else:
        recorder=Recorder(env,directory) if a.evaluate else TrainingRecorder(env,directory,lambda:agent._iter+iteration_offset)
    if a.omni_run_lr:recorder.phase_agent=agent
    control=json.loads((ROOT/'private.json').read_text())
    backups=Backups(directory,control['s3'],'mimickit/pipeline_20261014/runs/'+a.name)
    start=time.time()
    deadline=min(start+a.seconds,control['deadline_unix']-45)
    live_deadline=RuntimeDeadline(ROOT/'runtime_control.json',control['pod_id'],deadline+165,reserve=165)
    times=[]
    latest_test={}
    latest_train={}
    latest_losses=None
    evaluation_iteration=None
    last_snapshot=-1
    original_train_iter=agent._train_iter
    original_rollout_test=agent._rollout_test
    original_save=agent.save

    def snapshot(iteration,reason,final=False):
        nonlocal last_snapshot
        iteration+=iteration_offset
        if iteration==last_snapshot and not final:
            return
        # Never accumulate unverified checkpoints behind a failed/slow upload.
        # Normal background uploads finish well before the next save interval.
        backups.wait()
        begun=time.perf_counter()
        model=directory/'model.tmp.pt'
        original_save(str(model));model.replace(directory/'model.pt')
        state={'completed_iteration':iteration,'samples':agent._sample_count,
               'actor_optimizer':agent._actor_optimizer._optimizer.state_dict(),
               'critic_optimizer':agent._critic_optimizer._optimizer.state_dict(),
               'actor_steps':agent._actor_optimizer._steps,'critic_steps':agent._critic_optimizer._steps,
               'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all(),
               'numpy_rng':np.random.get_state(),'python_rng':random.getstate(),
               'normalizer_aux':{name:{key:getattr(mod,key) for key in ['_mean_sq','_new_count','_new_sum','_new_sum_sq']}
                                 for name,mod in agent.named_modules() if hasattr(mod,'_new_sum_sq')},
               'physics_episode_state_saved':False,'reason':reason}
        if is_amp:
            state['disc_optimizer']=agent._disc_optimizer._optimizer.state_dict()
            state['disc_steps']=agent._disc_optimizer._steps
            state['disc_replay_buffer_saved']=False
        if getattr(env,'_adaptive_rows',None) is not None:
            state['adaptive_rows']=env._adaptive_rows.state(env._fixed_motion_ids)
        torch.save(state,directory/'resume_state.pt')
        archive=directory/f"checkpoint_{iteration:07d}{'_final' if final else ''}.zip"
        with zipfile.ZipFile(archive.with_suffix('.tmp'),'w',compression=zipfile.ZIP_STORED) as z:
            if a.per_agent_noise:
                z.write(Path(__file__).with_name('agent_noise.py'),'agent_noise.py')
                z.write(directory/'agent_noise.json','agent_noise.json')
            for name in ['model.pt','resume_state.pt','engine_config.yaml','env_config.yaml','agent_config.yaml','provenance.json']:
                z.write(directory/name,name)
            z.write(ROOT/'runtime-freeze.txt','runtime-freeze.txt')
            for name in ['evaluation.json','replay.npz','resume.json','velocity_command_bounds.json','torque_envelope.json']:
                if (directory/name).exists():z.write(directory/name,name)
            if getattr(env,'_adaptive_rows',None) is not None:
                z.write(Path(__file__).with_name('adaptive_rows.py'),'adaptive_rows.py')
                for name in ('adaptive_rows.json','adaptive_rows.jsonl'):
                    if (directory/name).exists():z.write(directory/name,name)
            if a.task not in ('walk','amp'):
                z.write(Path(__file__).with_name(a.task+'.py'),a.task+'.py')
            if a.task in ('amp_standing','world_pose'):
                z.write(Path(__file__).with_name('networks.py'),'networks.py')
                for name in ('amp_standing_target.pkl','amp_standing_target.json'):
                    z.write(Path(__file__).with_name(name),name)
            if a.floor_impact_limit_n is not None:
                z.write(REPO/'mimickit/engines/newton_engine.py','newton_engine.py')
            if a.timed_best_tail:z.write(Path(__file__).with_name('timed_pose.py'),'timed_pose.py')
            if a.task=='recovery_pose':z.write(Path(__file__).with_name('neutral_pose.py'),'neutral_pose.py')
            if final:
                for path in directory.iterdir():
                    if path.name.startswith('events.out.tfevents.') or path.name=='log.txt':
                        z.write(path,path.name)
        archive.with_suffix('.tmp').replace(archive)
        backups.submit(archive)
        if last_snapshot < 0:
            # Prove durable storage works before continuing a new paid run.
            backups.wait()
        if hasattr(agent,'_logger') and agent._logger._writer:agent._logger._writer.flush()
        atomic_json(directory/'checkpoint_status.json',dict(iteration=iteration,path=archive.name,
            samples=agent._sample_count,bytes=archive.stat().st_size,local_save_seconds=time.perf_counter()-begun))
        last_snapshot=iteration

    def iteration():
        nonlocal latest_train, latest_losses, deadline
        if backups.errors:
            # Failed durable saves must not leave a paid trainer running for
            # hours. The exit watcher preserves local evidence and stops billing.
            raise RuntimeError('Checkpoint backup failed; stopping GPU. See backup_errors.json')
        deadline=live_deadline.read()
        if (ROOT/'stop.request').exists() or (directory/'stop.request').exists() or time.time()>=deadline:
            snapshot(agent._iter-1,'stop before next PPO update')
            raise StopRequested()
        begun=time.perf_counter()
        if record_training and agent._iter % a.output_interval == max(0,a.output_interval-3):recorder.arm()
        if a.profile and 5 <= agent._iter <= 7:
            from profile_training import run_profiled_update
            result=run_profiled_update(agent,original_train_iter,directory,agent._iter-5)
        else:
            result=original_train_iter()
        if not bool(torch.stack([torch.isfinite(p).all() for p in agent.parameters()]).all()):
            report_failure(dict(reason='Nonfinite model parameter after update; refusing checkpoint promotion'))
            raise FloatingPointError('Nonfinite model; previous verified checkpoints retained')
        if not math.isfinite(float(result['mean_return'])):
            atomic_json(directory/'numerical_failure.json',dict(iteration=agent._iter+iteration_offset,
                reason='nonfinite training return; previous verified checkpoints retained'))
            raise FloatingPointError('Nonfinite training return; stopped before further updates')
        latest_train=dict(result)
        if getattr(env,'_adaptive_rows',None) is not None:
            allocation=env._adaptive_rows.report(env._fixed_motion_ids)
            if allocation is not None:
                allocation.update(iteration=iteration_offset+agent._iter,updated_unix=time.time(),
                    motions=[Path(env._motion_lib.get_motion_file(i)).stem for i in range(env._motion_lib.get_num_motions())])
                atomic_json(directory/'adaptive_rows.json',allocation)
                with (directory/'adaptive_rows.jsonl').open('a') as out:
                    out.write(json.dumps(allocation,separators=(',',':'))+'\n')
                agent._logger._writer.add_scalar('sampling/reassigned_rows',allocation['reassigned'],
                    agent._sample_count+a.worlds*agent._steps_per_iter)
        if (a.timed_best_tail or a.task=='world_pose' or a.absolute_walk) and agent._iter % 10 == 0:
            latest_losses=env.take_completed_losses()
            if latest_losses is not None:
                if a.equipment_omni:
                    latest_losses['body_total']=latest_losses['total']
                    latest_losses['auto_phase']=float(result['auto_phase_weighted'])
                    latest_losses['total']+=latest_losses['auto_phase']
                for key,value in latest_losses.items():
                    agent._logger._writer.add_scalar('loss/'+key,value,agent._sample_count+a.worlds*agent._steps_per_iter)
                agent._logger._writer.flush()
        if record_training and recorder.ready:
            recorder.finish(agent._iter+iteration_offset,agent._sample_count+a.worlds*agent._steps_per_iter,
                extra_metadata=dict(**noise_metadata,
                    rollout_action_noise_std=rollout_sigma,worlds=a.worlds,
                    losses=({'total':-float(result['disc_reward_mean'])} if a.task=='amp_standing' else (latest_losses or {}) if a.timed_best_tail else dict(train_mse_m2=-float(result['mean_return']) if result.get('num_eps',0)>0 else None))))
        elapsed=time.perf_counter()-begun
        times.append(elapsed)
        recent=times[-30:]
        samples=resumed['prior_samples']+(agent._iter+1)*a.worlds*agent._steps_per_iter
        if agent._iter%10==0:
            values={k:float(v) for k,v in result.items() if isinstance(v,(float,int))}
            atomic_json(directory/'status.json',dict(state='training',iteration=iteration_offset+agent._iter,samples=samples,
                worlds=a.worlds,updated_unix=time.time(),elapsed_seconds=time.time()-start,
                iteration_seconds=elapsed,recent_iteration_mean_seconds=sum(recent)/len(recent),
                training_transitions_per_second=a.worlds*agent._steps_per_iter/(sum(recent)/len(recent)),
                metrics=values,losses=latest_losses,evaluation=latest_test,physics_cuda_graph=True,
                deadline_unix=deadline))
        return result

    def evaluate(num_episodes):
        nonlocal latest_test
        begun=time.perf_counter()
        if a.task=='amp_standing':
            # Upstream test mode uses actor.mode and completes an episode in
            # EVERY world. Record those existing steps; no additional rollout.
            recorder.start()
            try:
                result=original_rollout_test(num_episodes)
                replay=recorder.finish(iteration_offset+agent._iter,agent._sample_count,
                    dict(**noise_metadata,rollout_action_noise_std=0.,worlds=a.worlds,
                         losses={'total':-float(latest_train['disc_reward_mean']) if 'disc_reward_mean' in latest_train else None}))
            finally:
                recorder.suspend()
            latest_test=dict(result,iteration=iteration_offset+agent._iter,
                evaluation_seconds=time.perf_counter()-begun,replay=replay,
                note='Deterministic actor mode; training noise unchanged; environment return is zero')
            atomic_json(directory/'evaluation.json',latest_test)
            return result
        if a.task=='world_pose' or a.absolute_walk:
            train_totals=env._completed_loss_totals.clone()
            env._completed_loss_totals.zero_()
        if a.equipment_omni:
            recorder.world=0 if (agent._iter//a.output_interval)%2==0 else env._idle_rows
        recorder.start()
        try:
            result=original_rollout_test(num_episodes)
        finally:
            recorder.enabled=False
        recorded_iteration=iteration_offset+(agent._iter if evaluation_iteration is None else evaluation_iteration)
        replay_metrics=dict(**noise_metadata,
                            rollout_action_noise_std=0.0,worlds=a.worlds,control_mode=a.control_mode)
        if a.task in ('neutral_pose','world_pose'):
            replay_metrics['losses']=dict(
                train_mse_m2=-float(latest_train['mean_return']) if latest_train.get('num_eps',0)>0 else None,
                test_mse_m2=-float(result['mean_return']))
        if a.task=='world_pose' or a.absolute_walk:
            result['loss_terms']=env.take_completed_losses()
            env._completed_loss_totals.copy_(train_totals)
            replay_metrics['losses']=dict(total=(latest_losses or {}).get('total')) if a.absolute_walk else dict(total=replay_metrics['losses']['train_mse_m2'])
        if a.task=='amp':replay_metrics['task']='amp_spinkick'
        if a.task=='amp_standing':
            replay_metrics.update(task='amp_standing',start_side=recorder.start_side,
                upright_worlds=int(env._upright_cohort.sum()),early_termination='upright cohort only',
                terminal_meaning='1=failure (upright cohort only); 3=two-second timeout, not success',
                losses={'total':-float(latest_train['disc_reward_mean']) if 'disc_reward_mean' in latest_train else None})
        replay=recorder.finish(recorded_iteration,agent._sample_count,extra_metadata=replay_metrics)
        if a.task not in ('walk','amp','amp_standing'):
            replay['task']=env.task_name
            replay['terminal_meaning']=('two-second timeout, not recovery success' if a.task=='world_pose' else 'fixed 45-step horizon; not a recovery-success flag')
            if a.feet_lateral_termination:
                replay['terminal_meaning']=('1=feet spread failure with remaining-tick cost; 3=two-second timeout'
                    if a.termination_remaining_cost else '1=feet spread exceeds pelvis-lateral limit; 3=two-second timeout; no extra failure cost')
            if a.floor_impact_limit_n is not None:
                replay['terminal_meaning']='1=foot distance or selected-body floor impact failure with remaining-tick cost; 3=timeout'
            if a.task=='head_height': result['minimum_independent_peaks_mean_m']=result['mean_return']
            else:
                metric='episode_mean_body_position_mse_m2' if env.task_name=='continuous_neutral_pose_mse' else 'final_body_position_mse_mean_m2'
                if env.task_name=='best_neutral_pose_mse': metric='episode_best_body_position_mse_mean_m2'
                if a.task=='world_pose':metric=('episode_mean_worst_body_position_plus_orientation_mse' if a.worst_body else 'episode_mean_position_plus_orientation_mse')
                if a.height_band_calibration:metric='episode_mean_pose_plus_height_bands'
                if a.height_bands_only:metric='episode_mean_height_bands_only'
                if a.feet_lateral_calibration:metric='episode_mean_pose_height_and_feet_lateral'
                if a.feet_lateral_termination:metric='episode_accumulated_pose_height_loss_with_spread_termination'
                result[metric]=-result['mean_return']
        latest_test=dict(result,iteration=recorded_iteration,evaluation_seconds=time.perf_counter()-begun,replay=replay)
        atomic_json(directory/'evaluation.json',latest_test)
        return result

    def report_failure(detail):
        detail.update(iteration=agent._iter+iteration_offset,time=time.time(),run=a.name)
        atomic_json(directory/'numerical_failure.json',detail)
        print('TRAINING ALERT: '+json.dumps(detail),flush=True)
        if hasattr(agent,'_logger') and agent._logger._writer:
            agent._logger._writer.add_scalar('health/numerical_failure',1,agent._sample_count)
            agent._logger._writer.flush()
    from health import install_guard
    def report_solver_warning(detail):
        detail.update(iteration=agent._iter+iteration_offset,time=time.time(),run=a.name)
        atomic_json(directory/'solver_warnings.json',detail)
        print('SOLVER WARNING: '+json.dumps(detail),flush=True)
        if hasattr(agent,'_logger') and agent._logger._writer:
            for tag,key in [('solver_roundoff_warnings','roundoff_total'),('solver_convergence_warnings','convergence_total'),
                            ('solver_motor_residual_nm','maximum_motor_residual_nm'),
                            ('solver_contact_limit_velocity_residual','maximum_contact_limit_velocity_residual')]:
                agent._logger._writer.add_scalar('health/'+tag,detail[key],agent._sample_count)
            agent._logger._writer.flush()
    install_guard(agent,report_failure,report_solver_warning)
    agent._train_iter=iteration
    agent._rollout_test=evaluate
    agent._output_train_model=lambda it,*unused:snapshot(it,'upstream output interval')
    atomic_json(directory/'owner.json',dict(name=a.name,directory=str(directory),pid=os.getpid()))
    try:
        agent.train_model(a.max_samples if a.max_samples is not None else float('inf'),str(directory),False,'tb')
        final_state='completed'
    except StopRequested:
        final_state='stopped'
    except BaseException as error:
        # Preserve completed checkpoints; do not label an interrupted update as valid.
        failure=dict(time=time.time(),iteration=iteration_offset+agent._iter,reason=f'{type(error).__name__}: {error}')
        atomic_json(directory/'failure.json',failure)
        status_path=directory/'status.json'
        status=json.loads(status_path.read_text()) if status_path.exists() else {}
        atomic_json(status_path,dict(status,state='failed',failure=failure))
        capture=getattr(env._engine,'failure_capture',None)
        try:
            if capture is not None and int(capture.seen.numpy()[0]):
                capture.save(directory/'solver_failure.npz')
        except Exception as capture_error:
            atomic_json(directory/'failure_capture_error.json',dict(reason=str(capture_error)))
        raise
    finally:
        if hasattr(agent,'_logger') and agent._logger._writer:
            agent._logger._writer.flush()
        backups.wait()
    if (a.task!='walk' or a.omni_run_lr) and a.evaluate:
        # Finite 1.5s evaluation takes ~3s on this GPU. The deadline reserves
        # 165s for evaluation, upload, readback and shutdown.
        evaluation_iteration=agent._iter-1
        agent.test_model(agent._test_episodes)
        atomic_json(directory/'final_evaluation.json',latest_test)
        snapshot(agent._iter-1,'final evaluated policy',final=True)
        backups.wait()
    if not a.evaluate:
        snapshot(agent._iter-1,'final training state; no evaluation',final=True)
        backups.wait()
    if a.benchmark and time.time()<deadline-120:
        results=[]
        final_poses=[]
        action=torch.zeros((a.worlds,agent.get_action_size()),device='cuda:0')
        # Matched reset/action sequences; ABBA order and repeated measurements.
        # This is an observer microbenchmark, not a second training job.
        for enabled in [False,True,True,False,False,True]:
            torch.manual_seed(901)
            torch.cuda.manual_seed_all(901)
            recorder.enabled=False
            env.reset()
            for _ in range(8):env.step(action)
            recorder.count=0;recorder.enabled=enabled
            torch.cuda.synchronize()
            began=time.perf_counter()
            for _ in range(64):env.step(action)
            torch.cuda.synchronize()
            elapsed=time.perf_counter()-began
            results.append(dict(capture_enabled=enabled,seconds=elapsed,steps=64))
            final_poses.append(env._engine.get_body_pos(env._get_char_id()).clone())
        recorder.enabled=False
        difference=max(float((p-final_poses[0]).abs().max()) for p in final_poses[1:])
        off_repeat=max(float((final_poses[i]-final_poses[0]).abs().max()) for i in [3,4])
        on_repeat=max(float((final_poses[i]-final_poses[1]).abs().max()) for i in [2,5])
        before_pos=env._engine.get_body_pos(env._get_char_id()).clone()
        before_rot=env._engine.get_body_rot(env._get_char_id()).clone()
        recorder.count=0;recorder.capture()
        capture_mutates_state=not (torch.equal(before_pos,env._engine.get_body_pos(env._get_char_id()))
            and torch.equal(before_rot,env._engine.get_body_rot(env._get_char_id())))
        off=np.median([r['seconds'] for r in results if not r['capture_enabled']])
        on=np.median([r['seconds'] for r in results if r['capture_enabled']])
        atomic_json(directory/'benchmark.json',dict(worlds=a.worlds,train_update_seconds=times,
            steady_training_transitions_per_second=a.worlds*agent._steps_per_iter/np.median(times[5:]),
            observer_measurements=results,observer_median_overhead_percent=100*(on/off-1),
            repeated_reset_final_pose_max_difference=difference,
            repeated_capture_off_difference=off_repeat,repeated_capture_on_difference=on_repeat,
            capture_mutates_physics_state=capture_mutates_state,
            note='Timing comparison, not deterministic trajectory proof: stock resets can retain solver state. Observer copies run only during vanilla evaluation; zero capture during PPO collection.'))
    atomic_json(directory/'finished.json',dict(state=final_state,samples=agent._sample_count,
        iteration=iteration_offset+agent._iter,elapsed_seconds=time.time()-start))
    print('MIMICKIT_TRIAL_FINISHED',final_state,flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as error:
        if '--name' in sys.argv:
            failed_dir=ROOT/'runs'/sys.argv[sys.argv.index('--name')+1]
            if failed_dir.is_dir() and not (failed_dir/'failure.json').exists():
                atomic_json(failed_dir/'failure.json',dict(time=time.time(),reason=f'{type(error).__name__}: {error}'))
        print(f'TRAINING ALERT: {type(error).__name__}: {error}',flush=True)
        raise
