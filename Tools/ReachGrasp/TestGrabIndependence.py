"""Owned TestNN PIE: vary one held hand's independence and verify native scope."""
import json
import re
import time
import traceback
from pathlib import Path
import unreal


def begin():
    headless = '-ProphecyGrabCheck' in unreal.SystemLibrary.get_command_line()
    if headless:
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    assert not editor.get_game_world(), 'Active user Play preserved'
    assert editor.get_editor_world().get_path_name() == '/Game/testNN.testNN'
    out = Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/GrabIndependence'
    out.mkdir(parents=True, exist_ok=True)
    lib = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyReachLibrary'))
    old_fps = unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
    state = dict(world=None, start=time.monotonic(), rows=[], changes=0, last_tick=-1, joint=None)
    left, right = unreal.ProphecyReachHand.LEFT, unreal.ProphecyReachHand.RIGHT

    def finish(reason):
        unreal.unregister_slate_post_tick_callback(state['callback'])
        if state['world'] and editor.get_game_world() == state['world']:
            level.editor_request_end_play()
        state['world'] = None
        unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), f't.MaxFPS {old_fps}')
        result = dict(reason=reason, rows=state['rows'], changes=state['changes'])
        (out / 'runtime.json').write_text(json.dumps(result, indent=2))
        print('GRAB_INDEPENDENCE_FINISHED', reason)
        if headless:
            unreal.EditorPythonScripting.set_keep_python_script_alive(False)

    def tick(_):
        try:
            if time.monotonic() - state['start'] > 90:
                return finish('timeout')
            world = editor.get_game_world()
            if not world:
                if state['world']:
                    finish('ended externally')
                return
            if state['world'] is None:
                state['world'] = world
            if world != state['world']:
                return finish('world changed')
            agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
            agent = next((a for a in agents if a.get_editor_property('Left Grab Ball')), None)
            if not agent:
                return
            n = int(agent.get_editor_property('absolute tick debug'))
            if n == state['last_tick']:
                return
            state['last_tick'] = n
            status = lib.call_method('GetGrabStatus', args=(agent, left))
            if state['changes'] == 0 and not status.gripped:
                return
            if state['changes'] == 0:
                state['first_grip'] = n
                assert lib.call_method('SetGrabJointIndependence', args=(agent, right, .75))
                state['next'] = n
            if n < state['next']:
                return
            assert status.gripped and status.physical_grip, 'Grip lost during alpha change'
            sequence = [0., .25, .5, 1., 0.]
            index = state['changes']
            if index >= len(sequence):
                return finish('passed')
            alpha = sequence[index]
            assert lib.call_method('SetGrabJointIndependence', args=(agent, left, alpha))
            assert lib.call_method('GetGrabJointIndependence', args=(agent, left)) == alpha
            assert lib.call_method('GetGrabJointIndependence', args=(agent, right)) == .75
            assert not lib.call_method('SetGrabJointIndependence', args=(agent, left, 1.1))
            # Repeated Grab Bone changes the same live joint, preserving admission/motion.
            if index == 2:
                other = lib.call_method('GetClosestAgent', args=(agent,))
                mesh = other.call_method('GetPoseReferenceMesh')
                assert lib.call_method('GrabBone', args=(agent, left, mesh, unreal.Name('clavicle_r'), unreal.Vector(), 300., 360., False, alpha))
            unreal.SystemLibrary.execute_console_command(world, f'Prophecy.Reach.Inspect Independence {agent.get_name()}')
            report = (out / 'live.txt').read_text(encoding='utf-8-sig')
            lines = [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in report.splitlines()]
            physical = next(line for line in lines if line['side'] == '0')
            assert physical['read'] == '1' and float(physical['native']) == alpha, report
            joint = physical['slot'], physical['generation']
            if state['joint'] is not None:
                assert state['joint'] == joint, 'Joint identity changed'
            state['joint'] = joint
            state['rows'].append(dict(tick=n, alpha=alpha, native=lines))
            state['changes'] += 1
            state['next'] = n + 15
        except Exception:
            finish(traceback.format_exc())

    state['callback'] = unreal.register_slate_post_tick_callback(tick)
    level.editor_request_begin_play()
    print('GRAB_INDEPENDENCE_STARTED')


begin()
