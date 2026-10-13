"""Owned-PIE head/FPS diagnosis using current unsaved scene/Blueprint settings.

No asset writes. Optional controls affect owned PIE instances only. Restores
the temporary FPS cap. Switching mode during an active D/S cancels that action,
so that control cannot establish kinematic return parity.
"""
import argparse
import json
import math
import pathlib
import re
import time
import traceback
import unreal

parser = argparse.ArgumentParser()
parser.add_argument('--name', required=True)
parser.add_argument('--fps', type=float, required=True)
parser.add_argument('--ticks', type=int, default=460)
parser.add_argument('--kinematic', action='store_true')
parser.add_argument('--kinematic-at', type=int, default=6)
parser.add_argument('--no-head-feedback', action='store_true')
parser.add_argument('--feedback-at', type=int, default=150)
parser.add_argument('--light', action='store_true')
parser.add_argument('--arm', action='store_true', help='Capture reach jitter, right-arm bodies and equipment')
parser.add_argument('--free-head-limits', action='store_true')
parser.add_argument('--control-at', type=int, default=90)
parser.add_argument('--no-head-contacts', action='store_true')
parser.add_argument('--output', default='Saved/Diagnostics/SwordHeadFps20261011')
parser.add_argument('--draw-at', type=int, default=-1)
parser.add_argument('--start-at', type=int, default=-1, help='Owned PIE: replace tick25 action with a later start after locomotion settles')
parser.add_argument('--gaze', type=float, help='Temporary normalized UE yaw on owned PIE agents')
parser.add_argument('--motion', choices=['idle','walk','run','transition','turn'], default='idle')
parser.add_argument('--cycles', type=int, default=0, help='Automatically draw/sheathe after each completed action')
parser.add_argument('--gaze-change', action='store_true')
parser.add_argument('--pose-detail', action='store_true')
parser.add_argument('--no-action', action='store_true', help='Hide sword before the Blueprint trigger; locomotion control only')
parser.add_argument('--free-neck-on-exit', action='store_true', help='Diagnostic: suppress only restoration of neck angular modes')
parser.add_argument('--clear-lane', action='store_true', help='Disable only Cube collision in the owned PIE world')
parser.add_argument('--grip-stabilization', type=float, help='Owned manual-start profile, percent')
parser.add_argument('--holster-return', type=float, default=.25)
parser.add_argument('--shrink', type=float, help='Owned manual-start axial shrink override')
parser.add_argument('--solo', action='store_true', help='Owned PIE control: remove NPCs before the action')
args = parser.parse_args()
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world(), 'Existing Play is left untouched.'
root = pathlib.Path(unreal.Paths.project_dir())
out = root / args.output
out.mkdir(parents=True, exist_ok=True)
old_fps = unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), f't.MaxFPS {args.fps}')
state = dict(world=None, actors=[], rows=[], start=time.monotonic(), last=-1, mode_set=False, feedback_set=False)
swords = {}
physics_api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJoltStandardPhysicsLibrary')) if args.arm else None
profile = json.loads((root/'Content/locomotion/SwordHolsterProfile.json').read_text(encoding='utf-8-sig'))
profile = profile.get('parameters', profile)
speeds = (profile['maxReachSpeed'], profile['maxReachRotationSpeed'], profile['slidingSpeed'])
bones = ['pelvis', 'spine_05', 'neck_01', 'neck_02', 'head', 'hand_r']
if args.arm:
    bones += ['spine_01', 'spine_02', 'spine_03', 'spine_04', 'clavicle_r', 'upperarm_r', 'lowerarm_r']
if args.light:
    bones = ['spine_05', 'head']


def pose(t):
    p, q = t.translation, t.rotation
    return [p.x, p.y, p.z, q.x, q.y, q.z, q.w]


def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['callback'])
    if state['world'] and editor.get_game_world() == state['world']:
        level.editor_request_end_play()
    control_world = editor.get_game_world() or editor.get_editor_world()
    unreal.SystemLibrary.execute_console_command(control_world, f't.MaxFPS {old_fps}')
    result = {k: v for k, v in state.items() if k not in ['world', 'actors', 'start', 'callback']}
    result.update(reason=reason, options=vars(args), restored_fps=old_fps)
    (out / (args.name + '.json')).write_text(json.dumps(result, separators=(',', ':')), encoding='utf-8')
    print('HEAD_FPS_FINISHED', args.name, reason, 'rows', len(state['rows']))


def tick(_):
    try:
        if time.monotonic() - state['start'] > 180:
            return finish('timeout')
        world = editor.get_game_world()
        if not world:
            if state['world']:
                finish('world ended externally')
            return
        state['world'] = world
        if args.clear_lane and not state.get('lane_cleared'):
            obstacles=[a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor) if a.get_actor_label()=='Cube']
            assert len(obstacles)==1,'Expected one known run-lane obstacle'
            state['disabled_obstacle']=obstacles[0].get_path_name()
            # Notify both UE and the native scene importer explicitly. Destroying
            # an actor during initial physics admission is an unreliable fixture.
            for component in obstacles[0].get_components_by_class(unreal.PrimitiveComponent):
                component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            obstacles[0].set_actor_enable_collision(False)
            state['lane_cleared']=True
        player = unreal.GameplayStatics.get_player_pawn(world, 0)
        if not isinstance(player, unreal.ProphecyAgent):
            return
        if args.solo and not state.get('solo_set'):
            for actor in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent):
                if actor!=player:actor.destroy_actor()
            state['solo_set']=True
        n = int(player.get_editor_property('absolute tick debug'))
        if n == state['last']:
            return
        state['last'] = n
        if not state['actors']:
            state['actors'] = sorted(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent), key=lambda a: a.get_name())
            state['player'] = player.get_name()
        if (args.no_action or args.start_at>=0) and n >= 22 and not state.get('action_removed'):
            for actor in state['actors']: actor.hide_sword()
            swords.clear()
            state['action_removed']=n
        if args.start_at>=0 and n>=args.start_at-4 and not state.get('manual_equipped'):
            assert all(actor.equip_sword(not args.kinematic) for actor in state['actors'])
            state['manual_equipped']=n
        if args.start_at>=0 and n>=args.start_at and not state.get('manual_started'):
            api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySwordHolsterLibrary'))
            for actor in state['actors']:
                assert api.call_method('SetSwordHolsterLabProfile',args=(actor,'Content/locomotion/SwordHolsterProfile.json'))
                if args.grip_stabilization is not None or args.shrink is not None:
                    assert api.call_method('SetSwordHolsterProfile',args=(actor,args.shrink if args.shrink is not None else float(profile['shrinkPercent']),float(profile['unshrinkDuration']),args.grip_stabilization if args.grip_stabilization is not None else float(profile['holsterRotationStabilization'])*100,args.holster_return,float(profile['shrinkDuration']),float(profile['maxAttachedSpeed']),float(profile['maxAttachedRotationSpeed']),bool(profile['leewayPhase']),float(profile['sheatheTipTolerance'])))
                assert api.call_method('DrawSword',args=(actor,True,*speeds))
            state['manual_started']=n
        if args.draw_at >= 0 and n >= args.draw_at and not state.get('draw_requested'):
            api = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecySwordHolsterLibrary'))
            state['draw_requested'] = n
            state['draw_results'] = [[a.get_name(), api.call_method('DrawSword', args=(a, False, *speeds))] for a in state['actors']]
        if args.kinematic and not state['mode_set'] and n >= args.kinematic_at:
            for actor in state['actors']:
                assert actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            state['mode_set'] = True
        if args.gaze is not None and n >= 6 and not state.get('gaze_set'):
            for actor in state['actors']:
                actor.set_upper_nn_gaze(args.gaze, 0.)
            state['gaze_set'] = n
        if n >= 6:
            if not state.get('input_owned'):
                for actor in state['actors']:
                    unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',(actor,'disable auto locomotion debug',True))
                    if args.motion!='idle':
                        actor.set_locomotion_walk_checkpoint_speed_threshold(-1.)
                    if args.gaze is not None or args.gaze_change:
                        unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',(actor,'disable gaze debug',True))
                state['input_owned']=n
            if 'directions' not in state:
                state['directions'] = {a.get_name(): [a.get_actor_forward_vector().x,a.get_actor_forward_vector().y] for a in state['actors']}
            if args.motion == 'idle':
                for actor in state['actors']:
                    x,y = state['directions'][actor.get_name()]
                    actor.set_locomotion_input(unreal.Vector(),False,unreal.Vector(x,y,0),1.,1.)
            else:
                for actor in state['actors']:
                    x,y = state['directions'][actor.get_name()]
                    angle = max(0,n-75)*math.pi/360 if args.motion == 'turn' else 0
                    direction = unreal.Vector(x*math.cos(angle)-y*math.sin(angle),x*math.sin(angle)+y*math.cos(angle),0)
                    moving = args.motion != 'transition' or n%240 < 160
                    running = args.motion in ['walk','run','turn'] or (args.motion == 'transition' and n%240>=80)
                    # WalkF is the user's run checkpoint with input length .4.
                    actor.set_locomotion_input(direction*(.4 if args.motion=='walk' else 1.) if moving else unreal.Vector(), running, direction, 1. if running else .5, 1.)
            if args.gaze_change:
                for actor in state['actors']:
                    actor.set_upper_nn_gaze(.8*math.sin(n/90), 0.)
        if args.no_head_feedback and not state['feedback_set'] and n >= args.feedback_at:
            for actor in state['actors']:
                for bone in (['clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r'] if args.arm else ['neck_01', 'neck_02', 'head']):
                    assert actor.set_physical_feedback_tolerance(bone, 10000., 180.)
            state['feedback_set'] = True
        if args.free_head_limits and not state.get('limits_set') and n >= args.control_at:
            state['limits_results'] = []
            for actor in state['actors']:
                for bone in ['neck_01', 'head']:
                    result = actor.set_physical_joint_angular_limits(bone,
                        unreal.AngularConstraintMotion.ACM_FREE, 180.,
                        unreal.AngularConstraintMotion.ACM_FREE, 180.,
                        unreal.AngularConstraintMotion.ACM_FREE, 180.)
                    state['limits_results'].append([actor.get_name(), bone, str(result)])
            state['limits_set'] = n
        if args.no_head_contacts and not state.get('contacts_set') and n >= args.control_at:
            channels = [getattr(unreal.CollisionChannel, key) for key in dir(unreal.CollisionChannel)
                        if key.startswith('ECC_') and 0 <= getattr(unreal.CollisionChannel, key).value < 32]
            for actor in state['actors']:
                for channel in channels:
                    result = unreal.ProphecyLimbCollisionLibrary.set_jolt_limb_collision_response(
                        actor, 'neck_01', channel, unreal.CollisionResponseType.ECR_IGNORE, True)
                    assert result is not None, str(channel)
            state['contacts_set'] = n
        if n >= 18:
            fields = {}
            if not args.light or n % 10 == 0:
                unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Sword.HolsterReport')
                raw = (root / 'Saved/Diagnostics/SwordDraw20261010/state.txt').read_bytes()
                report = raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
                fields = {line.split()[0]: {k: float(v) for k, v in re.findall(r'(\w+)=(-?\d+(?:\.\d+)?)', line)} for line in report.splitlines() if line.strip()}
            row = dict(tick=n, wall=time.monotonic()-state['start'], dt=unreal.GameplayStatics.get_world_delta_seconds(world), actors={})
            if args.pose_detail:
                unreal.SystemLibrary.execute_console_command(world,'Prophecy.Sword.PoseReport')
                detail=json.loads((root/'Saved/Diagnostics/SwordOvernight20261011/pose-detail.json').read_text(encoding='utf-8-sig'))
            for actor in state['actors']:
                if args.free_neck_on_exit:
                    phase=fields.get(actor.get_name(),{}).get('phase',-1)
                    prior=state.setdefault('prior_phase',{}).get(actor.get_name(),-1)
                    if prior in (0,1,2,4) and phase in (-1,3):
                        for bone in ['neck_01','neck_02','head']:
                            actor.set_physical_joint_angular_limits(bone,unreal.AngularConstraintMotion.ACM_FREE,180.,unreal.AngularConstraintMotion.ACM_FREE,180.,unreal.AngularConstraintMotion.ACM_FREE,180.)
                    state['prior_phase'][actor.get_name()]=phase
                names, future, presented, alpha = actor.read_nn_future_world_pose()
                mesh = actor.get_pose_reference_mesh()
                values = dict(fields=fields.get(actor.get_name(), {}), alpha=alpha,
                              root=pose(actor.get_actor_transform()),
                              locomotion=str(actor.get_locomotion_state()),
                              gaze=[actor.upper_nn_gaze_yaw_normalized,actor.upper_nn_gaze_pitch_normalized],
                              future={str(k): pose(t) for k, t in zip(names, future) if str(k) in bones},
                              target={str(k): pose(t) for k, t in zip(names, presented) if str(k) in bones},
                              physical={k: pose(mesh.get_socket_transform(k)) for k in bones})
                if args.pose_detail:values['authored']=detail.get(actor.get_name())
                if n == 20:
                    values['names'] = [str(k) for k in names]
                    values['parents'] = [str(mesh.get_parent_bone(k)) for k in names]
                    values['head_feedback'] = str(actor.get_physical_feedback_tolerance('head'))
                    values['head_magnetization'] = str(actor.get_body_magnetization_settings('head'))
                    values['neck_magnetization'] = str(actor.get_body_magnetization_settings('neck_01'))
                    lib = unreal.ConstraintInstanceBlueprintLibrary
                    values['joints'] = []
                    for constraint in mesh.get_constraints(True):
                        pair = [str(x) for x in lib.get_attached_body_names(constraint)[1:]]
                        if set(pair) & ({'neck_01', 'neck_02', 'head', 'clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r'} if args.arm else {'neck_01', 'neck_02', 'head'}):
                            values['joints'].append([pair, str(lib.get_angular_limits(constraint)[1:])])
                if not args.light:
                    values['native'] = {}
                    for bone in (['pelvis','neck_01','neck_02','head','clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r'] if args.arm else ['neck_01', 'neck_02', 'head']):
                        body = actor.get_physical_body_state(bone)
                        if body:
                            tr, velocity, angular, sim = body
                            values['native'][bone] = dict(pose=pose(tr), v=[velocity.x, velocity.y, velocity.z],
                                w=[angular.x, angular.y, angular.z], sim=sim)
                if args.arm:
                    values['equipment'] = {}
                    values['equipment_scale'] = {}
                    for comp in actor.get_components_by_class(unreal.StaticMeshComponent):
                        if comp.get_name().lower() == 'holster':
                            values['equipment']['holster'] = pose(comp.get_world_transform())
                            values['holster_local']=pose(comp.get_relative_transform())
                            values['holster_absolute_rotation']=comp.get_editor_property('absolute_rotation')
                            vel=physics_api.call_method('GetPhysicsLinearVelocityAtPoint',args=(comp,comp.get_world_transform().translation,unreal.Name('None')))
                            ang=physics_api.call_method('GetPhysicsAngularVelocityInRadians',args=(comp,unreal.Name('None')))
                            values['holster_velocity']=[vel.x,vel.y,vel.z,ang.x,ang.y,ang.z]
                    held = actor.get_held_sword()
                    if held:
                        swords[actor.get_name()] = held
                    sword = swords.get(actor.get_name()) if args.start_at<0 or state.get('manual_equipped') else None
                    if sword:
                        for comp in sword.get_components_by_class(unreal.StaticMeshComponent):
                            values['equipment'][comp.get_name()] = pose(comp.get_world_transform())
                            if comp == sword.get_editor_property('root_component'):
                                parent = comp.get_attach_parent()
                                values['sword_parent'] = parent.get_path_name() if parent else None
                                values['sword_local'] = pose(comp.get_relative_transform())
                            scale=comp.get_world_transform().scale3d
                            values['equipment_scale'][comp.get_name()]=[scale.x,scale.y,scale.z]
                row['actors'][actor.get_name()] = values
            state['rows'].append(row)
            if args.cycles and n >= 26 and (args.start_at<0 or state.get('manual_started')):
                api = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecySwordHolsterLibrary'))
                actions = state.setdefault('actions', {})
                for actor in state['actors']:
                    name = actor.get_name(); phase = fields.get(name,{}).get('phase',-1)
                    action = actions.setdefault(name, {'draw':False, 'cycles':0, 'last_request':state.get('manual_started',25)})
                    if n <= action['last_request']+4 or action['cycles'] >= args.cycles: continue
                    if not action['draw'] and phase == 3:
                        if args.grip_stabilization is not None:
                            assert api.call_method('SetSwordHolsterProfile',args=(actor,args.shrink if args.shrink is not None else float(profile['shrinkPercent']),float(profile['unshrinkDuration']),args.grip_stabilization,args.holster_return,float(profile['shrinkDuration']),float(profile['maxAttachedSpeed']),float(profile['maxAttachedRotationSpeed']),bool(profile['leewayPhase']),float(profile['sheatheTipTolerance'])))
                        assert api.call_method('DrawSword', args=(actor, False, *speeds))
                        action.update(draw=True,last_request=n)
                    elif action['draw'] and phase == -1:
                        action['cycles'] += 1
                        if action['cycles'] < args.cycles:
                            assert api.call_method('DrawSword', args=(actor, True, *speeds))
                            action.update(draw=False,last_request=n)
                if all(a['cycles'] >= args.cycles for a in actions.values()):
                    state.setdefault('completed_tick',n)
                    if n>=state['completed_tick']+30:return finish('cycles completed')
        if n >= args.ticks:
            finish('captured')
    except Exception:
        finish(traceback.format_exc())


state['callback'] = unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('HEAD_FPS_STARTED', args.name, args.fps)
