"""Transient full/half attack clamp switching and handoff check. No asset writes."""
import builtins
import json
import pathlib
import traceback
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
state = dict(actors=[], phase=0, samples=0)
builtins._attack_hand_clamp_check = state

def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['callback'])
    (pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/SlashContacts/AttackHandClampSmoke.json').write_text(
        json.dumps(dict(reason=reason, samples=state['samples'])), encoding='utf-8')
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('ATTACK_HAND_CLAMP_CHECK', reason)

def tick(_):
    try:
        world = editor.get_game_world()
        if not world:
            return
        now = unreal.GameplayStatics.get_time_seconds(world)
        if not state['actors']:
            state['actors'] = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent) if a.get_agent_handle().index in (0,2)]
            assert len(state['actors']) == 2
            for actor in state['actors']:
                actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
                actor.set_actor_tick_enabled(False)
                actor.stop_nn_attack()
                assert actor.set_attack_hand_clamp(True, 0)
                assert not actor.set_attack_hand_clamp(True, -1)
            state['actors'][0].set_nn_interpolation_mode(unreal.ProphecyNNInterpolationMode.HERMITE_SLERP)
        if now < .8:
            for actor in state['actors']:
                actor.stop_nn_attack()
        if now >= 1 and state['phase'] == 0:
            for i, actor in enumerate(state['actors']):
                assert actor.trigger_nn_attack('hookR',actor.get_root_low_point()+unreal.Vector(-30,50,115),bool(i))
                assert actor.set_attack_hand_clamp(True,1)
            state['phase'] = 1
        if now >= 1.5 and state['phase'] == 1:
            for actor in state['actors']:
                assert actor.set_attack_hand_clamp(False,1)
            state['phase'] = 2
        if now >= 1.75 and state['phase'] == 2:
            for actor in state['actors']:
                before = actor.read_nn_future_world_pose()
                actor.stop_nn_attack()
                after = actor.read_nn_future_world_pose()
                assert before and after and before[0] == after[0]
                for a,b in zip(before[2],after[2]):
                    assert (a.translation-b.translation).length() < .001, 'Handoff moved interpolated pose'
                assert actor.set_attack_hand_clamp(True,0)
            state['phase'] = 3
        for actor in state['actors']:
            if actor.read_nn_future_world_pose():
                state['samples'] += 1
        if now >= 2.2:
            assert state['samples'] > 10
            finish('passed')
    except Exception:
        finish(traceback.format_exc())

state['callback'] = unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
