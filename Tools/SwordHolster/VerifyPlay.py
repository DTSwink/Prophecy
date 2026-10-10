"""Owned-PIE D/S regression. Never saves or edits an asset.

Run through Tools/RunUnrealRemote.py. Default uses the saved tick25 sequence.
An explicit --shrink-percent cancels/re-equips and changes only the PIE instance.
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
parser.add_argument('--name', default='final-sim')
parser.add_argument('--kinematic', action='store_true')
parser.add_argument('--walk', action='store_true')
parser.add_argument('--shrink-percent', type=float)
parser.add_argument('--repeat', type=int, default=1)
parser.add_argument('--unshrink', type=float, default=.5)
parser.add_argument('--pause', action='store_true')
parser.add_argument('--switch-back', action='store_true')
parser.add_argument('--cancel-phase', type=int, choices=[1, 2, 4])
args = parser.parse_args()
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world(), 'An existing Play session is never interrupted.'
root = pathlib.Path(unreal.Paths.project_dir())
out = root / 'Saved/Diagnostics/SwordLabPort20261010'
api = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecySwordHolsterLibrary'))
state = {'world': None, 'last': -1, 'start': time.monotonic(), 'rows': [], 'events': [], 'cycles': 0, 'drawing': False}


def command(world, text):
    unreal.SystemLibrary.execute_console_command(world, text)


def report(world, actor):
    command(world, 'Prophecy.Sword.HolsterReport')
    raw = (out.parent / 'SwordDraw20261010/state.txt').read_bytes()
    text = raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
    return next(line for line in text.splitlines() if line.startswith(actor.get_name() + ' '))


def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['callback'])
    world = editor.get_game_world()
    if world and world == state['world']:
        if state.get('pause_until'):
            unreal.GameplayStatics.set_game_paused(world, False)
        level.editor_request_end_play()
    result = {k: v for k, v in state.items() if k not in ['world', 'callback', 'sword', 'start']}
    result.update(reason=reason, options=vars(args))
    (out / (args.name + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('HOLSTER_VERIFY_FINISHED', args.name, reason)


channels = [getattr(unreal.CollisionChannel, n) for n in dir(unreal.CollisionChannel)
            if n.startswith('ECC_') and 0 <= getattr(unreal.CollisionChannel, n).value < 32]
right = ['upperarm_r', 'lowerarm_r', 'hand_r']
left = ['upperarm_l', 'lowerarm_l', 'hand_l', 'spine_03']


def filters(actor, bones):
    return {bone: {str(c): [str(x) for x in unreal.ProphecyLimbCollisionLibrary.get_jolt_limb_collision_response(actor, bone, c)[:2]]
                   for c in channels} for bone in bones}


def vec(v):
    return [v.x, v.y, v.z]


def quat(q):
    return [q.x, q.y, q.z, q.w]


def tick(_):
    try:
        if time.monotonic() - state['start'] > 180:
            finish('wall timeout')
            return
        world = editor.get_game_world()
        if not world:
            if state['world']:
                finish('world ended externally')
            return
        state['world'] = world
        actor = unreal.GameplayStatics.get_player_pawn(world, 0)
        if not isinstance(actor, unreal.ProphecyAgent):
            return
        n = int(actor.get_editor_property('absolute tick debug'))
        if state.get('pause_until'):
            assert n == state['pause_tick'], 'Game tick advanced while paused'
            assert report(world, actor) == state['pause_report'], 'D/S advanced while paused'
            if time.monotonic() >= state['pause_until']:
                unreal.GameplayStatics.set_game_paused(world, False)
                state['pause_until'] = None
                state['events'].append([n, 'pause verified'])
            return
        if n == state['last']:
            return
        state['last'] = n
        if args.walk and n >= 20:
            if 'walk_direction' not in state:
                state['walk_direction'] = vec(actor.get_actor_forward_vector())
            forward = unreal.Vector(*state['walk_direction'])
            actor.set_locomotion_input(forward, False, forward, .5, 1.)
        if state.get('switch_tick'):
            if n >= state['switch_tick'] + 60:
                h = next(x for x in actor.get_components_by_class(unreal.PrimitiveComponent) if x.get_name() == 'holster')
                lib = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyJoltStandardPhysicsLibrary'))
                assert lib.call_method('IsSimulatingPhysics', args=(h, unreal.Name('None'))), 'Holster simulation was not restored'
                assert actor.get_editor_property('simulation_mode') == unreal.ProphecyAgentSimulationMode.PHYSICAL
                gap = math.dist(vec(h.get_world_transform().translation), vec(actor.get_pose_reference_mesh().get_socket_location('pelvis')))
                assert abs(gap - state['holster_pelvis_distance']) < 15, 'Holster fell away after mode restoration'
                state['restored_holster_pelvis_distance'] = gap
                state['events'].append([n, 'Sim and holster simulation restored'])
                finish('passed')
            return
        if not args.kinematic and n >= 20 and not state.get('collision_before'):
            state['collision_before'] = filters(actor, right)
            state['collision_unrelated'] = filters(actor, left)
        if args.kinematic and n >= 6 and not state.get('mode_set'):
            assert actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            state['mode_set'] = True
        if args.shrink_percent is not None:
            if n >= 26 and not state.get('cancelled_prefix'):
                actor.hide_sword()
                state['cancelled_prefix'] = n
            if not state.get('restarted'):
                if n < state.get('cancelled_prefix', n) + 4:
                    return
                if not actor.equip_sword(not args.kinematic):
                    return
                state['restarted'] = n
                return
            if not state.get('manual_start'):
                if n < state['restarted'] + 3:
                    return
                assert api.call_method('SetSwordHolsterLabProfile', args=(actor, 'Content/locomotion/SwordHolsterProfile.json'))
                assert api.call_method('SetSwordHolsterProfile', args=(actor, args.shrink_percent, args.unshrink))
                assert api.call_method('DrawSword', args=(actor, True, 250., 2500., 150.))
                state['manual_start'] = n
                state['events'].append([n, 'explicit diagnostic sheathe'])
        if n < 26:
            return
        line = report(world, actor)
        fields = {key: float(value) for key, value in re.findall(r'(\w+)=(-?\d+(?:\.\d+)?)', line)}
        phase = int(fields['phase'])
        if not state.get('sword'):
            state['sword'] = actor.get_held_sword()
            assert state['sword'], 'No sword at test entry'
        names, future, presented, alpha = actor.read_nn_future_world_pose()
        mesh = actor.get_pose_reference_mesh()
        selected = ['pelvis', 'spine_05', 'clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r', 'head']
        poses = {str(k): t for k, t in zip(names, presented) if str(k) in selected}
        nn = {k: vec(t.translation) for k, t in poses.items()}
        physical = {k: vec(mesh.get_socket_location(k)) for k in selected}
        row = dict(tick=n, state=line, fields=fields, nn=nn, physical=physical,
                   nn_q={k: quat(t.rotation) for k, t in poses.items()},
                   physical_q={k: quat(mesh.get_socket_transform(k).rotation) for k in selected},
                   tracking_error=math.dist(nn['hand_r'], physical['hand_r']),
                   parent=str(state['sword'].root_component.get_attach_parent() if state['sword'].root_component else None),
                   mode=str(actor.get_editor_property('simulation_mode')))
        state['rows'].append(row)
        if state.get('last_phase') != phase:
            state['events'].append([n, 'draw' if state['drawing'] else 'sheathe', phase])
            state['last_phase'] = phase
        if phase in [1, 2, 4]:
            assert bool(fields['kinematic']) == args.kinematic, 'Unexpected runtime mode'
        if not args.kinematic:
            assert filters(actor, left) == state['collision_unrelated'], 'Unrelated collision changed'
            if phase in [0, 1, 2, 4]:
                assert all(value[1] == str(unreal.CollisionResponseType.ECR_IGNORE)
                           for values in filters(actor, right).values() for value in values.values())
                state['suppression_checks'] = state.get('suppression_checks', 0) + 1
            else:
                assert filters(actor, right) == state['collision_before'], 'Right-arm collision not restored'
        if phase == 2 and not state.get('duplicates_checked'):
            for _ in range(5):
                assert api.call_method('DrawSword', args=(actor, not state['drawing'], 250., 2500., 150.))
            assert report(world, actor) == line, 'Duplicate calls changed the transfer or joint'
            state['duplicates_checked'] = True
        if args.cancel_phase == phase and not state.get('cancel_tick'):
            actor.hide_sword()
            state['cancel_tick'] = n
            state['events'].append([n, 'hide cancellation'])
        if state.get('cancel_tick'):
            if n >= state['cancel_tick'] + 5:
                assert phase == -1 and fields['joint'] == 0 and not actor.get_held_sword()
                finish('passed cancellation')
            return
        if args.pause and phase == 4 and not state.get('pause_tested'):
            state.update(pause_tested=True, pause_tick=n, pause_report=line, pause_until=time.monotonic() + .75)
            assert unreal.GameplayStatics.set_game_paused(world, True)
            return
        if phase == 3 and not state['drawing']:
            assert fields['joint'] == 0 and fields['attached'] == 1
            state['drawing'] = True
            assert api.call_method('DrawSword', args=(actor, False, 250., 2500., 150.))
        elif phase == -1 and state['drawing']:
            assert actor.get_held_sword() == state['sword'], 'Sword actor was replaced'
            assert fields['joint'] == 0
            state['cycles'] += 1
            if state['cycles'] >= args.repeat:
                if args.switch_back and args.kinematic:
                    h = next(x for x in actor.get_components_by_class(unreal.PrimitiveComponent) if x.get_name() == 'holster')
                    state['holster_pelvis_distance'] = math.dist(vec(h.get_world_transform().translation), vec(mesh.get_socket_location('pelvis')))
                    assert actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
                    state['switch_tick'] = n
                    return
                finish('passed')
                return
            state['drawing'] = False
            assert api.call_method('DrawSword', args=(actor, True, 250., 2500., 150.))
        if fields['pose_tick'] > 550 or n > 550 * (state['cycles'] + 1):
            finish('geometric or physical stall')
    except Exception:
        finish(traceback.format_exc())


out.mkdir(parents=True, exist_ok=True)
state['callback'] = unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('HOLSTER_VERIFY_STARTED', args.name)
