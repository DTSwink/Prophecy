"""PIE-only GT-family admission, retained-state mode switches and cleanup checks."""
import builtins
import json
import pathlib
import time
import traceback
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
s = dict(last=-1, actor=None, phase=0, rows=[], wall=time.perf_counter(), family=-1)
builtins._half_lifecycle = s
families = ['slashL', 'slashR', 'slashLD', 'slashRD', 'slashLU', 'slashRU',
            'pike', 'jabL', 'jabR', 'hookL', 'hookR', 'overL', 'overR', 'headbutt']


def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['callback'])
    w = editor.get_game_world()
    if w:
        unreal.SystemLibrary.execute_console_command(w, 'Prophecy.SlashTestHalfUpperSource -1')
    path = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/SlashContacts/HalfLifecycle.json'
    path.write_text(json.dumps(dict(reason=reason, rows=s['rows']), indent=2))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('HALF_LIFECYCLE', reason)


def tick(dt):
    try:
        w = editor.get_game_world()
        if not w:
            return
        t = unreal.GameplayStatics.get_time_seconds(w)
        if t == s['last']:
            return
        s['last'] = t
        if s['actor'] is None:
            actors = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ProphecyAgent)
            for a in actors:
                a.set_actor_tick_enabled(False)
                a.stop_nn_attack()
                a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            s['actor'] = next(a for a in actors if a.get_agent_handle().index == 0)
            unreal.SystemLibrary.execute_console_command(w, 'Prophecy.SlashTestHalfUpperSource 0')
        a = s['actor']
        target = a.get_root_low_point() + unreal.Vector(-30, 50, 115)
        if t >= 0.5 and s['phase'] == 0:
            assert a.trigger_nn_attack('headbutt', target, True)
            s['phase'] = 1
        for at, phase, half in [(0.6, 1, False), (0.7, 2, True), (0.8, 3, True)]:
            if t >= at and s['phase'] == phase:
                before = a.get_nn_attack_state()
                assert before and a.set_nn_half_attack_enabled(half)
                after = a.get_nn_attack_state()
                assert after[1] == half and before[2:] == after[2:]
                s['rows'].append(dict(t=t, operation='mode', half=half, before=str(before), after=str(after)))
                s['phase'] += 1
        if t >= 1.0 and s['phase'] == 4:
            a.stop_nn_attack()
            assert not a.get_nn_attack_state()
            s['phase'] = 5
        index = int((t - 1.2) / 0.25) if t >= 1.2 else -1
        if 0 <= index < len(families) and index != s['family']:
            s['family'] = index
            assert a.trigger_nn_attack(families[index], target, True)
            before = a.get_nn_attack_state()
            assert before and before[1] and before[-1] == 1
            for invalid in ['kickL', 'kickR', 'not_an_attack']:
                assert not a.trigger_nn_attack(invalid, target, True)
                assert a.get_nn_attack_state() == before
            s['rows'].append(dict(t=t, operation='family', family=families[index], accepted=True))
        if t > 5:
            assert s['family'] == len(families) - 1 and s['phase'] == 5
            a.stop_nn_attack()
            finish('Complete')
        elif time.perf_counter() - s['wall'] > 90:
            finish('Timeout')
    except Exception:
        finish(traceback.format_exc())


s['callback'] = unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('HALF_LIFECYCLE_STARTED')
