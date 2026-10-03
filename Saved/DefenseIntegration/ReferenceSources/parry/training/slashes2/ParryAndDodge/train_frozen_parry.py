"""Fresh upper-only Parry experiment. Captured training only, no eager fallback.

As in the existing full-motion trainer, each update consumes fresh episodes.
Confirmed success sets each row's logical terminal frame; later graph slots
have no loss/gradient and are omitted from playback. Rows are resampled for the
next update, with no wait for authored time and no state carried across rows.
Fixed padded graph work is retained, not recaptured for every contact time.
Optional authored-or-previous required contact scores its two timestamps even
after an earlier protected contact; the other losses retain their terminal mask.
"""
import argparse
from dataclasses import asdict, replace
from datetime import datetime
import json
import math
import os
from pathlib import Path
import secrets
import time
import torch
from torch.utils.tensorboard import SummaryWriter
import prepare_transition_corpus as corpus
from frozen_parry_sampling import WeaponMeleeSampler as BalancedSampler, CONTRACT as SAMPLING_CONTRACT
from frozen_parry_blade_plane import FrozenWeights as Weights,CONTRACT as BLADE_PLANE_CONTRACT
from frozen_parry_blade_center import CONTRACT as BLADE_CENTER_CONTRACT
from frozen_parry_blade_center import ATTACKER_CONTRACT as ATTACKER_BLADE_CENTER_CONTRACT
from transition_replayer import payload, write, LOSS_NAMES as BASE_LOSS_NAMES
from transition_features import TARGET_CONTRACT
from transition_self_collision import CONTRACT as SELF_COLLISION_CONTRACT,NO_UPPERARM_CONTRACT as FULL_ARM_CONTRACT
from transition_run_deadline import RunDeadline
from train_transition_smoke import ControllerGraph, atomic_json, save, RUNS
from frozen_parry_agent import CHECKPOINT_KIND, DRAWN_CONTRACT, rollout
from frozen_parry_forearm_center import CONTRACT as FOREARM_CENTER_CONTRACT
from frozen_parry_upperarm_zone import CONTRACT as UPPERARM_ZONE_CONTRACT
from frozen_parry_forearm_direction import CONTRACT as FOREARM_DIRECTION_CONTRACT
from frozen_parry_contact_target import CONTRACT as CONTACT_TARGET_CONTRACT
from frozen_parry_behind_chest import CONTRACT as BEHIND_CHEST_CONTRACT
from frozen_parry_elbow_pole import CONTRACT as ELBOW_POLE_CONTRACT
from frozen_parry_spine_yaw import CONTRACT as SPINE_YAW_CONTRACT
from frozen_parry_gaze import CONTRACT as GAZE_CONTRACT, HEIGHT_AUDIT
from frozen_parry_success_self_harm import CONTRACT as SUCCESS_SELF_HARM_CONTRACT
from frozen_parry_blade_velocity import CONTRACT as BLADE_VELOCITY_CONTRACT
from frozen_parry_attacker_edge import CONTRACT as ATTACKER_EDGE_CONTRACT
from frozen_parry_block_clearance import CONTRACT as BLOCK_CLEARANCE_CONTRACT
from frozen_parry_early_contact import CONTRACT as EARLY_CONTACT_CONTRACT
from frozen_parry_spine_tilt import CONTRACT as SPINE_TILT_CONTRACT
from frozen_parry_control_smoothness import CONTRACT as CONTROL_SMOOTHNESS_CONTRACT
from frozen_parry_spine_limits import CONTRACT as SPINE_LIMITS_CONTRACT, SPEED_LIMIT_DEG, YAW_LIMIT_DEG
from frozen_parry_free_hand_idle import CONTRACT as FREE_HAND_IDLE_CONTRACT, IDLE_SOURCE, IDLE_SHA256, IDLE_LOCAL
from attacker_pelvis_cylinder import CONTRACT as ATTACKER_CYLINDER_CONTRACT
from frozen_parry_upperarm_inward import CONTRACT as UPPERARM_INWARD_CONTRACT
from frozen_parry_batch import FrozenMotionBank
from frozen_parry_collision import CONTRACT, FreeTimingConfig
from frozen_parry_resume import changed_weights, validate_checkpoint, resume_indices
from transition_resume import restore_captured_optimizer

LOSS_NAMES=(*BASE_LOSS_NAMES,'blade_plane','blade_center','forearm_center','upperarm_zone','forearm_direction','contact_target','behind_chest','elbow_pole','spine_yaw','upperarm_inward','attacker_blade_center','gaze','success_self_harm','blade_velocity','attacker_edge','block_clearance')
LOSS_NAMES=(*LOSS_NAMES,'early_contact','spine_tilt','control_smoothness')
LOSS_NAMES=(*LOSS_NAMES,'spine_angvel','free_hand_idle')


def checked_weights(reference):
    if reference['kind'] != 'parry': raise ValueError('Parry weight reference required')
    return replace(Weights(**reference['weights']), predictive_pin=0., anti_pin_slide=0.)


@torch.no_grad()
def check_dynamic_rows(bank, runner, indices):
    """Same graph, every raw label and shortest/longest rows; no retained update."""
    selected = []
    for raw in sorted({r['row']['motion_kind'] for r in bank.rows}):
        selected.append(next(i for i,r in enumerate(bank.rows) if r['row']['motion_kind']==raw))
    selected += [min(range(len(bank.rows)),key=lambda i:bank.rows[i]['length']),
                 max(range(len(bank.rows)),key=lambda i:bank.rows[i]['length'])]
    for raw in sorted({r['row']['motion_kind'] for r in bank.rows}):
        for drawn in (False,True):
            match=next((i for i,r in enumerate(bank.rows) if r['row']['motion_kind']==raw
                and r['record']['scene']['drawn']==drawn),None)
            if match is not None and match not in selected:selected.append(match)
    checks=[];batch=len(indices)
    for i in selected:
        bank.select([i]*batch)
        torch.testing.assert_close(bank.agent.defender_drawn,bank.drawn[i].expand(batch),atol=0,rtol=0)
        assert bool((bank.objective.present[:,bank.objective.blade_index]==bank.drawn[i].bool()).all())
        if bank.objective.block_time is not None:
            torch.testing.assert_close(bank.objective.block_time,bank.extra['block_time'][i].expand(batch),atol=0,rtol=0)
        runner.backward_graph.replay()
        oracle=bank.objective(rollout(bank.agent,bank.selected),bank.selected)
        torch.testing.assert_close(runner.loss['total'],oracle['total'],atol=2e-6,rtol=2e-5)
        for key in ('terminal_frame','interval_valid'):
            torch.testing.assert_close(runner.loss[key],oracle[key],atol=0,rtol=0)
        for key,source in bank.blade_planes.items():
            torch.testing.assert_close(getattr(bank.objective,key),source[i:i+1].expand_as(getattr(bank.objective,key)),atol=0,rtol=0)
        torch.testing.assert_close(runner.loss['raw']['blade_plane'],oracle['raw']['blade_plane'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['blade_center'],oracle['raw']['blade_center'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['attacker_blade_center'],oracle['raw']['attacker_blade_center'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['gaze'],oracle['raw']['gaze'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['success_self_harm'],oracle['raw']['success_self_harm'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['blade_velocity'],oracle['raw']['blade_velocity'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['attacker_edge'],oracle['raw']['attacker_edge'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['block_clearance'],oracle['raw']['block_clearance'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['early_contact'],oracle['raw']['early_contact'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['spine_tilt'],oracle['raw']['spine_tilt'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['control_smoothness'],oracle['raw']['control_smoothness'],atol=2e-4,rtol=2e-5)
        for key in ('spine_angvel','free_hand_idle'):
            torch.testing.assert_close(runner.loss['raw'][key],oracle['raw'][key],atol=2e-5,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['forearm_center'],oracle['raw']['forearm_center'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['upperarm_zone'],oracle['raw']['upperarm_zone'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['forearm_direction'],oracle['raw']['forearm_direction'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['contact_target'],oracle['raw']['contact_target'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['behind_chest'],oracle['raw']['behind_chest'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['elbow_pole'],oracle['raw']['elbow_pole'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['spine_yaw'],oracle['raw']['spine_yaw'],atol=2e-6,rtol=2e-5)
        torch.testing.assert_close(runner.loss['raw']['upperarm_inward'],oracle['raw']['upperarm_inward'],atol=2e-6,rtol=2e-5)
        owned=bank.agent.lower_indices
        for name,expected in (('positions',bank.agent.cached_positions),('rotations',bank.agent.cached_rotations)):
            actual=getattr(runner.result,name).index_select(2,owned)
            target=expected.index_select(2,owned)
            torch.testing.assert_close(actual[bank.selected.valid],target[bank.selected.valid],atol=0,rtol=0)
        if not all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in runner.parameters):
            raise FloatingPointError('Nonfinite upper gradient during dynamic graph audit')
        checks.append(dict(pack_index=i,raw=bank.rows[i]['row']['motion_kind'],length=bank.rows[i]['length'],
            loss=float(oracle['total']),frozen_joints_bit_exact=True,
            block_time_routed=bank.objective.block_time is not None))
    bank.select(indices)
    return checks


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-name',required=True)
    p.add_argument('--pack',type=Path,required=True)
    p.add_argument('--lower-cache',type=Path,required=True)
    p.add_argument('--priors',type=Path,required=True)
    p.add_argument('--anti-statuing-root',type=Path,required=True)
    p.add_argument('--reference-config',type=Path,required=True,help='Weights only; no policy or Adam restored')
    p.add_argument('--batch-size',type=int,default=16)
    p.add_argument('--seed',type=int)
    p.add_argument('--resume',type=Path)
    p.add_argument('--allow-resume-batch-size-change',action='store_true')
    p.add_argument('--calf-weight',type=float)
    p.add_argument('--forearm-scale',type=float,default=1.)
    p.add_argument('--self-harm-weight',type=float)
    p.add_argument('--left-hand-self-harm-weight',type=float)
    p.add_argument('--blade-plane-weight',type=float)
    p.add_argument('--blade-center-weight',type=float)
    p.add_argument('--forearm-center-weight',type=float)
    p.add_argument('--upperarm-zone-weight',type=float)
    p.add_argument('--forearm-direction-weight',type=float)
    p.add_argument('--contact-target-weight',type=float)
    p.add_argument('--behind-chest-weight',type=float)
    p.add_argument('--elbow-pole-weight',type=float)
    p.add_argument('--spine-yaw-weight',type=float)
    p.add_argument('--upperarm-inward-weight',type=float)
    p.add_argument('--attacker-blade-center-weight',type=float)
    p.add_argument('--gaze-weight',type=float)
    p.add_argument('--success-self-harm-weight',type=float)
    p.add_argument('--blade-velocity-weight',type=float)
    p.add_argument('--attacker-edge-weight',type=float)
    p.add_argument('--block-clearance-weight',type=float)
    p.add_argument('--early-contact-weight',type=float)
    p.add_argument('--spine-tilt-weight',type=float)
    p.add_argument('--control-smoothness-weight',type=float)
    p.add_argument('--spine-angvel-weight',type=float)
    p.add_argument('--free-hand-idle-weight',type=float)
    p.add_argument('--stop-deadline-utc',help='Preserve an existing absolute stop deadline across restart')
    p.add_argument('--required-block-timing',choices=('free','authored_or_previous'))
    p.add_argument('--full-arm-self-harm',action='store_true',default=None)
    p.add_argument('--run-seconds',type=float,default=0.,help='Wall-clock training duration after graph checks; 0 means unbounded')
    p.add_argument('--steps',type=int,default=0)
    p.add_argument('--check-only',action='store_true')
    p.add_argument('--fixed-motion-index',type=int)
    p.add_argument('--runs-root',type=Path,default=RUNS)
    p.add_argument('--log-every',type=int,default=25)
    p.add_argument('--replayer-seconds',type=float,default=120.)
    p.add_argument('--checkpoint-seconds',type=float,default=300.)
    args=p.parse_args()
    datetime.strptime(args.run_name[:15],'%Y%m%d_%H%M%S')
    if Path(args.run_name).name!=args.run_name or args.batch_size<1 or args.steps<0 or args.log_every<1:
        raise ValueError('Invalid run settings')
    if min(args.replayer_seconds,args.checkpoint_seconds)<=0: raise ValueError('Positive export intervals required')
    if not math.isfinite(args.run_seconds) or args.run_seconds<0:raise ValueError('Invalid run duration')
    if args.fixed_motion_index is not None and args.batch_size!=1: raise ValueError('Fixed-motion smoke uses batch1')
    if args.resume and args.fixed_motion_index is not None:raise ValueError('Full-dataset resume cannot select a fixed motion')
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    if not torch.cuda.is_available(): raise RuntimeError('CUDA graphs required; no eager/CPU training')
    resumed=torch.load(args.resume,map_location='cpu',weights_only=False) if args.resume else None
    reference=resumed['config'] if resumed else corpus.read(args.reference_config)
    args.required_block_timing=args.required_block_timing or (reference.get('required_block_timing','free') if resumed else 'free')
    args.full_arm_self_harm=bool(args.full_arm_self_harm or (reference.get('full_arm_self_harm',False) if resumed else False))
    if resumed:
        validate_checkpoint(resumed,corpus.digest(args.pack),corpus.digest(args.lower_cache))
        if args.seed is not None and args.seed!=reference['seed']:raise ValueError('Resume retains the saved seed/RNG')
        weights=changed_weights(reference['weights'],args.calf_weight,args.forearm_scale,
            self_harm_weight=args.self_harm_weight,left_hand_self_harm_weight=args.left_hand_self_harm_weight,
            blade_plane_weight=args.blade_plane_weight,blade_center_weight=args.blade_center_weight)
    else:
        weights=changed_weights(asdict(checked_weights(reference)),args.calf_weight,args.forearm_scale,
            self_harm_weight=args.self_harm_weight,left_hand_self_harm_weight=args.left_hand_self_harm_weight,
            blade_plane_weight=args.blade_plane_weight,blade_center_weight=args.blade_center_weight)
    args.seed=reference['seed'] if resumed else (args.seed if args.seed is not None else 20260907)
    if args.forearm_center_weight is not None:
        if not math.isfinite(args.forearm_center_weight) or args.forearm_center_weight<0:raise ValueError('Invalid forearm-center weight')
        weights=replace(weights,forearm_center=args.forearm_center_weight)
    if args.upperarm_zone_weight is not None:
        if not math.isfinite(args.upperarm_zone_weight) or args.upperarm_zone_weight<0:raise ValueError('Invalid upperarm-zone weight')
        weights=replace(weights,upperarm_zone=args.upperarm_zone_weight)
    if args.forearm_direction_weight is not None:
        if not math.isfinite(args.forearm_direction_weight) or args.forearm_direction_weight<0:raise ValueError('Invalid forearm-direction weight')
        weights=replace(weights,forearm_direction=args.forearm_direction_weight)
    if args.contact_target_weight is not None:
        if not math.isfinite(args.contact_target_weight) or args.contact_target_weight<0:raise ValueError('Invalid contact-target weight')
        weights=replace(weights,contact_target=args.contact_target_weight)
    if args.behind_chest_weight is not None:
        if not math.isfinite(args.behind_chest_weight) or args.behind_chest_weight<0:raise ValueError('Invalid behind-chest weight')
        weights=replace(weights,behind_chest=args.behind_chest_weight)
    if args.elbow_pole_weight is not None:
        if not math.isfinite(args.elbow_pole_weight) or args.elbow_pole_weight<0:raise ValueError('Invalid elbow-pole weight')
        weights=replace(weights,elbow_pole=args.elbow_pole_weight)
    if args.spine_yaw_weight is not None:
        if not math.isfinite(args.spine_yaw_weight) or args.spine_yaw_weight<0:raise ValueError('Invalid spine-yaw weight')
        weights=replace(weights,spine_yaw=args.spine_yaw_weight)
    run=args.runs_root/args.run_name
    if args.upperarm_inward_weight is not None:
        if not math.isfinite(args.upperarm_inward_weight) or args.upperarm_inward_weight<0:raise ValueError('Invalid upperarm-inward weight')
        weights=replace(weights,upperarm_inward=args.upperarm_inward_weight)
    if run.exists(): raise FileExistsError('Run exists; use a new full datetime name')
    if args.attacker_blade_center_weight is not None:
        if not math.isfinite(args.attacker_blade_center_weight) or args.attacker_blade_center_weight<0:raise ValueError('Invalid attacker-blade-center weight')
        weights=replace(weights,attacker_blade_center=args.attacker_blade_center_weight)
    run.mkdir(parents=True);(run/'checkpoints').mkdir()
    if args.blade_velocity_weight is not None:
        if not math.isfinite(args.blade_velocity_weight) or args.blade_velocity_weight<0:raise ValueError('Invalid blade-velocity weight')
        weights=replace(weights,blade_velocity=args.blade_velocity_weight)
    if args.attacker_edge_weight is not None:
        if not math.isfinite(args.attacker_edge_weight) or args.attacker_edge_weight<0:raise ValueError('Invalid attacker-edge weight')
        weights=replace(weights,attacker_edge=args.attacker_edge_weight)
    if args.block_clearance_weight is not None:
        if not math.isfinite(args.block_clearance_weight) or args.block_clearance_weight<0:raise ValueError('Invalid block-clearance weight')
        weights=replace(weights,block_clearance=args.block_clearance_weight)
    if args.early_contact_weight is not None:
        if not math.isfinite(args.early_contact_weight) or args.early_contact_weight<0:raise ValueError('Invalid early-contact weight')
        weights=replace(weights,early_contact=args.early_contact_weight)
    if args.spine_tilt_weight is not None:
        if not math.isfinite(args.spine_tilt_weight) or args.spine_tilt_weight<0:raise ValueError('Invalid spine-tilt weight')
        weights=replace(weights,spine_tilt=args.spine_tilt_weight)
    if args.control_smoothness_weight is not None:
        if not math.isfinite(args.control_smoothness_weight) or args.control_smoothness_weight<0:raise ValueError('Invalid control-smoothness weight')
        weights=replace(weights,control_smoothness=args.control_smoothness_weight)
    for key in ('spine_angvel','free_hand_idle'):
        value=getattr(args,key+'_weight')
        if value is not None:
            if not math.isfinite(value) or value<0:raise ValueError('Invalid '+key+' weight')
            weights=replace(weights,**{key:value})
    if args.success_self_harm_weight is not None:
        if not math.isfinite(args.success_self_harm_weight) or args.success_self_harm_weight<0:raise ValueError('Invalid success-self-harm weight')
        weights=replace(weights,success_self_harm=args.success_self_harm_weight)
    if args.gaze_weight is not None:
        if not math.isfinite(args.gaze_weight) or args.gaze_weight<0:raise ValueError('Invalid gaze weight')
        weights=replace(weights,gaze=args.gaze_weight)
    marker=run/'debug/training.active.json';atomic_json(marker,dict(pid=os.getpid(),run_id=run.name))
    state=dict(state='initializing',pid=os.getpid(),step=0,run_id=run.name,kind='parry',batch_size=args.batch_size)
    atomic_json(run/'status.json',state);step=0;writer=None
    try:
        bank=FrozenMotionBank(args.pack,args.lower_cache)
        sampler=BalancedSampler(bank.rows,args.seed)
        indices=(resume_indices(resumed,sampler,args.batch_size,args.allow_resume_batch_size_change) if resumed else
            [args.fixed_motion_index] if args.fixed_motion_index is not None else sampler.sample(args.batch_size))
        agent,episode,objective=bank.setup(indices,weights,args.priors,args.seed,run,args.anti_statuing_root,args.required_block_timing,args.full_arm_self_harm)
        if resumed:agent.load_state_dict(resumed['model'],strict=True)
        def models(root,reference_key):
            result={name:dict(path=str(root/name/'best.pt'),sha256=corpus.digest(root/name/'best.pt')) for name in bank.types}
            if any(item['sha256']!=reference[reference_key][name]['sha256'] for name,item in result.items()):
                raise ValueError('Prior checkpoint differs from the previous Parry run')
            return result
        config=dict(schema=CHECKPOINT_KIND,kind='parry',run_id=run.name,seed=args.seed,batch_size=args.batch_size,
            fixed_motion=args.fixed_motion_index is not None,weights=asdict(weights),restart_from_scratch=resumed is None,
            resume_checkpoint=str(args.resume) if resumed else None,
            resume_checkpoint_sha256=corpus.digest(args.resume) if resumed else None,
            resume_step=int(resumed['step']) if resumed else None,
            resume_batch_size=int(reference['batch_size']) if resumed else None,
            resume_weight_changes={k:dict(before=reference['weights'].get(k,0.),after=v) for k,v in asdict(weights).items()
                if reference['weights'].get(k,0.)!=v},
            weight_reference=dict(path=str(args.reference_config),sha256=corpus.digest(args.reference_config)),
            training_pack=str(args.pack),training_pack_sha256=corpus.digest(args.pack),dataset_motions=len(bank.rows),
            frozen_lower_cache=str(args.lower_cache),frozen_lower_cache_sha256=corpus.digest(args.lower_cache),
            frozen_lower_provenance=bank.cache['provenance'],frozen_lower_audit=bank.cache['audit'],
            prior_checkpoints=models(args.priors,'prior_checkpoints'),
            anti_statuing_checkpoints=models(args.anti_statuing_root,'anti_statuing_checkpoints'),
            prior_scored_channels='upper90 only; lower context detached',
            frozen_agents=True,lower_trainable=False,upper_input=258,upper_output=90,lower_input=None,
            defender_drawn_contract=DRAWN_CONTRACT,forearm_center_contract=FOREARM_CENTER_CONTRACT,
            upperarm_zone_contract=UPPERARM_ZONE_CONTRACT,
            forearm_direction_contract=FOREARM_DIRECTION_CONTRACT,
            contact_target_contract=CONTACT_TARGET_CONTRACT,
            behind_chest_contract=BEHIND_CHEST_CONTRACT,self_harm_upperarms=False,
            elbow_pole_contract=ELBOW_POLE_CONTRACT,
            spine_yaw_contract=SPINE_YAW_CONTRACT,
            upperarm_inward_contract=UPPERARM_INWARD_CONTRACT,
            resume_spine_yaw_change=(dict(before=reference.get('spine_yaw_contract'),after=SPINE_YAW_CONTRACT)
                if resumed and reference.get('spine_yaw_contract')!=SPINE_YAW_CONTRACT else None),
            sword_presence='weapon_parry_always_drawn_else_scene_drawn_including_right_arm_blocks',
            policy_hidden=512,policy_layers=2,root='authored',pin_supervision=False,pin_loss=False,pose_mse=False,
            target_contract=TARGET_CONTRACT,self_collision_contract=FULL_ARM_CONTRACT if args.full_arm_self_harm else SELF_COLLISION_CONTRACT,
            full_arm_self_harm=args.full_arm_self_harm,run_seconds=args.run_seconds,
            stop_deadline_utc=args.stop_deadline_utc,blade_plane_contract=BLADE_PLANE_CONTRACT,
            resume_orientation_change=(dict(before=reference.get('blade_plane_contract'),after=BLADE_PLANE_CONTRACT)
                if resumed and reference.get('blade_plane_contract')!=BLADE_PLANE_CONTRACT else None),
            blade_center_contract=BLADE_CENTER_CONTRACT,
            attacker_blade_center_contract=ATTACKER_BLADE_CENTER_CONTRACT,
            gaze_contract=GAZE_CONTRACT,gaze_height_audit=None,
            gaze_target_source='episode.collider[:,2:,:3]',gaze_cone_degrees=5.,
            resume_gaze_change=(dict(before=reference.get('gaze_contract'),after=GAZE_CONTRACT)
                if resumed and reference.get('gaze_contract')!=GAZE_CONTRACT else None),
            success_self_harm_contract=SUCCESS_SELF_HARM_CONTRACT,
            blade_velocity_contract=BLADE_VELOCITY_CONTRACT,
            attacker_edge_contract=ATTACKER_EDGE_CONTRACT,
            block_clearance_contract=BLOCK_CLEARANCE_CONTRACT,
            early_contact_contract=EARLY_CONTACT_CONTRACT,
            spine_tilt_contract=SPINE_TILT_CONTRACT,
            control_smoothness_contract=CONTROL_SMOOTHNESS_CONTRACT,
            spine_limits_contract=SPINE_LIMITS_CONTRACT,
            spine_angvel_limit_deg_s=SPEED_LIMIT_DEG,
            free_hand_idle_contract=FREE_HAND_IDLE_CONTRACT,
            free_hand_idle_reference=dict(source=IDLE_SOURCE,sha256=IDLE_SHA256,frame=0,local_rotations=IDLE_LOCAL),
            attacker_cylinder_contract=ATTACKER_CYLINDER_CONTRACT,
            forearm_collider_override=objective.geometry.forearm_override,
            collider_contract=CONTRACT,collision_settings=asdict(FreeTimingConfig()),harness=objective.geometry.harness_identity,
            required_block_timing=args.required_block_timing,
            required_block_contract=(__import__('frozen_parry_timed_block').CONTRACT if args.required_block_timing=='authored_or_previous' else CONTRACT),
            required_block_after_early_terminal=args.required_block_timing=='authored_or_previous',
            defense_label_input=False,controller_input='two primers; initial root command; attacker current/end; completed frozen lower step',
            graph=True,graph_data_loading=True,eager_training=False,amp=False,tf32=False,
            sampling=SAMPLING_CONTRACT,sampling_audit=sampler.audit(),
            resume_sampling_change=(dict(before=reference.get('sampling'),after=SAMPLING_CONTRACT,
                saved_pending_batch_retained=True) if resumed and reference.get('sampling')!=SAMPLING_CONTRACT else None),
            leg_block_replacement={'22':'left arm, original sword presence','23':'right arm, original sword presence'},
            row_reset='fresh episode per update; success terminates each row at blocker-first contact, later padded work unscored',
            optimizer=dict(kind='AdamW',learning_rate=1e-4,decay_step=200,final_learning_rate=1e-5,gradient_clip=1.,weight_decay=0.),
            replayer_rows=min(args.batch_size,16),replayer_seconds=args.replayer_seconds,
            checkpoint_seconds=args.checkpoint_seconds,automatic_checkpoint_downloads=False)
        atomic_json(run/'config.json',config)
        state['state']='capturing_and_checking_graphs';atomic_json(run/'status.json',state);print(json.dumps(state),flush=True)
        initial_model={k:v.detach().clone() for k,v in agent.state_dict().items()} if resumed is None else None
        runner=ControllerGraph(agent,episode,objective,rollout_fn=rollout)
        report=runner.check();report['data_loading_graph']=bank.load_graph is not None
        report['dynamic_rows']=check_dynamic_rows(bank,runner,indices)
        report['only_upper_parameters']=all(n.startswith('upper.') for n,_ in agent.named_parameters())
        if initial_model is not None:
            for key,value in agent.state_dict().items():
                torch.testing.assert_close(value,initial_model[key],atol=0,rtol=0)
            for state_value in runner.optimizer.state.values():
                for key in ('step','exp_avg','exp_avg_sq'):
                    if bool(torch.count_nonzero(state_value[key])):raise ValueError('Fresh optimizer was modified by graph checks')
            report['fresh_init']=dict(step=0,model_unchanged_by_checks=True,adam_steps_and_moments_zero=True)
            del initial_model
        atomic_json(run/'graph_check.json',report);print(json.dumps(dict(graph_check=report)),flush=True)
        if resumed:
            restored=restore_captured_optimizer(runner.optimizer,resumed['optimizer'])
            step=int(resumed['step']);runner.lr.fill_(1e-4 if step<200 else 1e-5)
            torch.set_rng_state(resumed['cpu_rng']);torch.cuda.set_rng_state(resumed['cuda_rng'])
            for key,value in agent.state_dict().items():
                torch.testing.assert_close(value,resumed['model'][key].to(value.device),atol=0,rtol=0)
            restored.update(step=step,model_restored_exactly=True,rng_restored=True,
                old_batch_size=len(resumed['batch_indices']),new_batch_size=len(indices),
                saved_pending_rows_retained=bool((indices[:len(resumed['batch_indices'])]==resumed['batch_indices']).all()),
                extra_rows_from_saved_sampler=len(indices)-len(resumed['batch_indices']),
                weight_changes=config['resume_weight_changes'])
            atomic_json(run/'resume_check.json',restored);print(json.dumps(dict(resume_check=restored)),flush=True)
        if args.check_only:
            state.update(state='check_passed');atomic_json(run/'status.json',state);return
        writer=SummaryWriter(str(run/'tensorboard'),flush_secs=10)
        deadline=RunDeadline(args.run_seconds,args.stop_deadline_utc);state.update(deadline.metadata())
        atomic_json(run/'run_deadline.json',deadline.metadata())
        started=last_log=time.perf_counter();last_step=initial_step=step;last_replay=last_cp=-float('inf')
        best=float(resumed['best']) if resumed and not config['resume_weight_changes'] and not config['resume_orientation_change'] and args.full_arm_self_harm==reference.get('full_arm_self_harm',False) and args.required_block_timing==reference.get('required_block_timing','free') else float('inf')
        def checkpoint():
            live={**config,'motion':bank.rows[int(indices[0])]['row'],'motions':[bank.rows[int(i)]['row'] for i in indices]}
            return dict(kind=CHECKPOINT_KIND,config=live,model=agent.state_dict(),optimizer=runner.optimizer.state_dict(),
                step=step,best=best,sampler=sampler.state_dict(),batch_indices=indices,
                cpu_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state())
        while True:
            runner.backward_graph.replay()
            timed_out=deadline.expired()
            stopping=timed_out or (args.steps>0 and step>=args.steps) or (run/'stop.request').exists()
            if stopping:state['stop_reason']='run_duration_elapsed' if timed_out else 'requested_or_step_limit'
            if step%args.log_every==0 or stopping or step==initial_step:
                values=torch.stack([runner.loss['total'],*[runner.loss['weighted'][k].mean() for k in LOSS_NAMES],
                    *[runner.loss['raw'][k].mean() for k in LOSS_NAMES]]).detach().cpu().tolist()
                if not all(math.isfinite(v) for v in values): raise FloatingPointError('Nonfinite loss; not saved')
                now=time.perf_counter();rate=(step-last_step)/max(now-last_log,1e-8);last_log=now;last_step=step
                success=float(runner.loss['events'].protected.float().mean())
                terminal=float(runner.loss['terminal_frame'].float().mean())
                state.update(state='stopped' if stopping else 'running',step=step,loss=values[0],steps_per_second=rate,
                    motions_per_second=rate*args.batch_size,elapsed_seconds=now-started,
                    weapon_sample_fraction=float(sampler.weapon[indices].mean()),
                    updated_at=datetime.now().astimezone().isoformat(),success_fraction=success,mean_terminal_frame=terminal,
                    unresolved_pairs=int(runner.loss['events'].unresolved_pairs.sum()),
                    batch_motion_ids=[bank.rows[int(i)]['row']['id'] for i in indices],
                    cuda_reserved_gib=torch.cuda.memory_reserved()/2**30)
                for name,value in zip(('total',*LOSS_NAMES),values): writer.add_scalar('loss/'+name,value,step)
                for name,value in zip(LOSS_NAMES,values[len(LOSS_NAMES)+1:]): writer.add_scalar('raw/'+name,value,step)
                for name,value in dict(steps_per_second=rate,motions_per_second=rate*args.batch_size).items():
                    writer.add_scalar('performance/'+name,value,step)
                writer.add_scalar('contact/success_fraction',success,step);writer.add_scalar('contact/terminal_frame',terminal,step)
                writer.flush();atomic_json(run/'status.json',state);print(json.dumps(state),flush=True)
                if now-last_replay>=args.replayer_seconds or stopping:
                    write(run/'replayer',payload(runner.result,episode,objective,runner.loss,
                        bank.cases(indices[:16]),step=step,run_id=run.name));last_replay=now
                if now-last_cp>=args.checkpoint_seconds or stopping:
                    if values[0]<best: best=values[0];save(run/'checkpoints/best.pt',checkpoint())
                    save(run/'checkpoints/latest.pt',checkpoint())
                    if step==initial_step: save(run/'checkpoints/init.pt',checkpoint())
                    last_cp=now
            if stopping: break
            if step==200: runner.lr.fill_(1e-5)
            runner.optimizer_graph.replay();step+=1
            if args.fixed_motion_index is None: indices=sampler.sample(args.batch_size);bank.select(indices)
        # Published only AFTER the final checkpoint and rollout have been saved.
        # The remote billing watchdog can observe this even if PID1 leaves a zombie.
        atomic_json(run/'completion.json',dict(status='completed',step=step,
            stop_reason=state['stop_reason'],completed_at=datetime.now().astimezone().isoformat()))
    except BaseException as exc:
        state.update(state='failed',step=step,error=str(exc));atomic_json(run/'status.json',state);raise
    finally:
        if writer is not None: writer.close()
        if marker.exists(): marker.unlink()


if __name__=='__main__': main()
