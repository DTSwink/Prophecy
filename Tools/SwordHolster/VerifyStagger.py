"""Owned-PIE crowd admission/cancellation regression; no asset writes.

Uses the existing NPCs, a temporary 25% shrink fixture and the normal runtime.
Run through Tools/RunUnrealRemote.py, optionally with --kinematic.
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
parser.add_argument('--kinematic', action='store_true')
args = parser.parse_args()
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world(), 'Existing user Play is left untouched.'
root = pathlib.Path(unreal.Paths.project_dir())
out = root / 'Saved/Diagnostics/SwordStagger20261011'
out.mkdir(parents=True, exist_ok=True)
api = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecySwordHolsterLibrary'))
state = dict(world=None, start=time.monotonic(), last=-1, rows=[], events=[], actors=[], stage='setup')


def reports():
    unreal.SystemLibrary.execute_console_command(state['world'], 'Prophecy.Sword.HolsterReport')
    raw = (root / 'Saved/Diagnostics/SwordDraw20261010/state.txt').read_bytes()
    text = raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
    return {line.split()[0]: {k: float(v) for k, v in re.findall(r'(\w+)=(-?\d+(?:\.\d+)?)', line)}
            for line in text.splitlines() if line.strip()}


def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['callback'])
    if state['world'] and editor.get_game_world() == state['world']:
        if state.get('pause_until'):
            unreal.GameplayStatics.set_game_paused(state['world'], False)
        level.editor_request_end_play()
    result = {k: v for k, v in state.items() if k not in ['world', 'actors', 'callback', 'start']}
    result.update(reason=reason, kinematic=args.kinematic)
    (out / ('crowd-kinematic.json' if args.kinematic else 'crowd-sim.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('STAGGER_CROWD_FINISHED', reason)


def draw(actor, sheathe):
    return api.call_method('DrawSword', args=(actor, sheathe, 250., 2500., 150.))


def configure(actor):
    assert api.call_method('SetSwordHolsterLabProfile', args=(actor, 'Content/locomotion/SwordHolsterProfile.json'))
    assert api.call_method('SetSwordHolsterProfile', args=(actor, 25., .5))


def tick(_):
    try:
        if time.monotonic() - state['start'] > 180:
            return finish('wall timeout')
        world = editor.get_game_world()
        if not world:
            if state['world']:
                finish('world ended externally')
            return
        state['world'] = world
        player = unreal.GameplayStatics.get_player_pawn(world, 0)
        if not isinstance(player, unreal.ProphecyAgent):
            return
        n = int(player.get_editor_property('absolute tick debug'))
        if state.get('pause_until'):
            assert n == state['pause_tick'] and reports() == state['pause_report'], 'Queued action advanced while paused'
            if time.monotonic() >= state['pause_until']:
                unreal.GameplayStatics.set_game_paused(world, False)
                state['pause_until'] = None
                state['events'].append([n, 'queued pause verified'])
            return
        if n == state['last']:
            return
        state['last'] = n
        if not state['actors']:
            state['actors'] = sorted([a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
                                      if a != player], key=lambda a: a.get_name())
            if len(state['actors']) < 2:
                return
            state['actors'] = state['actors'][:2]
            state['names'] = [a.get_name() for a in state['actors']]
        actors = state['actors']
        if args.kinematic and n >= 6 and not state.get('mode_set'):
            for a in actors:
                assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            state['mode_set'] = True
        if n >= 26 and not state.get('cleared'):
            for a in actors:
                a.hide_sword()
            state['cleared'] = n
            return
        if not state.get('equipped'):
            if n >= state.get('cleared', n) + 4:
                for a in actors:
                    assert a.equip_sword(not args.kinematic)
                    configure(a)
                state['equipped'] = n
            return
        if state['stage'] == 'setup':
            if n < state['equipped'] + 3:
                return
            before = reports()
            for a in actors:
                assert draw(a, True)
            after = reports()
            queued = [a for a in actors if after[a.get_name()]['queued']]
            assert queued, 'Fixture did not exercise delayed crowd admission'
            for a in queued:
                f = after[a.get_name()]
                assert f['phase'] == -1 and f['joint'] == 0 and f['scale'] == 1 and f['refresh_slot'] >= 0
                assert a.get_held_sword(), 'Waiting changed sword ownership'
                for _ in range(5):
                    assert draw(a, True)
                assert not draw(a, False), 'Opposite queued request accepted'
            assert reports() == after, 'Duplicate request changed queue or runtime'
            state['request_tick'] = n
            state['stage'] = 'sheathing'
            state['events'].append([n, 'simultaneous S requests', after])
            state.update(pause_tick=n, pause_report=after, pause_until=time.monotonic() + .5)
            assert unreal.GameplayStatics.set_game_paused(world, True)
            return
        current = reports()
        fields = {a.get_name(): current[a.get_name()] for a in actors}
        state['rows'].append(dict(tick=n, fields=fields))
        for a in actors:
            f = fields[a.get_name()]
            assert all(math.isfinite(v) for v in f.values()), 'Non-finite runtime state'
            if state['stage'] == 'sheathing' and n >= state['request_tick'] + 3:
                assert not f['queued'], 'Admission exceeded three active ticks'
            if f['phase'] in [1, 2, 4]:
                assert bool(f['kinematic']) == args.kinematic
        if state['stage'] == 'sheathing' and all(f['phase'] == 3 for f in fields.values()):
            for a in actors:
                assert fields[a.get_name()]['joint'] == 0
                assert draw(a, False)
            queued = reports()
            waiting = [a for a in actors if queued[a.get_name()]['queued']]
            assert waiting, 'Fixture did not exercise queued drawing cancellation'
            victim = waiting[-1]
            victim.hide_sword()
            f = reports()[victim.get_name()]
            assert f['phase'] == -1 and f['queued'] == 0 and f['refresh_slot'] == -1 and f['joint'] == 0
            state['cancelled_name'] = victim.get_name()
            state['stage'] = 'drawing'
            state['events'].append([n, 'queued D cancelled; other D continues'])
        elif state['stage'] == 'drawing' and all(f['phase'] == -1 for f in fields.values()):
            for a in actors:
                f = fields[a.get_name()]
                assert f['queued'] == 0 and f['refresh_slot'] == -1 and f['joint'] == 0
                assert bool(a.get_held_sword()) == (a.get_name() != state['cancelled_name'])
            state['events'].append([n, 'D complete; all slots/joints released'])
            finish('passed')
        if n > 500:
            finish('geometric or physical stall')
    except Exception:
        finish(traceback.format_exc())


state['callback'] = unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('STAGGER_CROWD_STARTED', 'kinematic' if args.kinematic else 'sim')
