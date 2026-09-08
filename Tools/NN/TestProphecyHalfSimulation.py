"""PIE-only three-mode regression on an existing, registered manual pose agent.

Ends PIE after testing; never saves or edits the map/Blueprint assets.
"""
import json
import math
import traceback
from pathlib import Path
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_game_world() or unreal.EditorLevelLibrary.get_game_world()
assert world, "Start testNN PIE first"
agent = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
             if a.get_editor_property('manual_nn_pose_application') and a.has_valid_agent_handle())
mesh = agent.get_pose_reference_mesh()
native = agent.get_editor_property('PhysicalAnimation')
class mode:
    KINEMATIC = 'Kinematic'
    HALF_SIM = 'HalfSim'
    PHYSICAL = 'Physical'
bones = ['pelvis', 'calf_r', 'hand_r', 'foot_r']
initial_meshes = len(agent.get_components_by_class(unreal.SkeletalMeshComponent))
state = {'callback': None, 'phase': -1, 'start': 0., 'last_time': -1., 'rows': [], 'transitions': []}
phases = [mode.KINEMATIC, mode.HALF_SIM, mode.PHYSICAL, mode.HALF_SIM,
          mode.KINEMATIC, mode.PHYSICAL, mode.HALF_SIM, mode.KINEMATIC,
          mode.PHYSICAL, mode.KINEMATIC]
report = Path(unreal.Paths.project_saved_dir()).resolve() / 'NativePhysical/pose_agent_three_modes.json'

def body_states():
    return {bone: agent.get_physical_body_state(bone) for bone in bones}

def xyz(v):
    return [v.x, v.y, v.z]

def active_mode():
    if not mesh.is_simulating_physics('pelvis'):
        return mode.KINEMATIC
    return mode.HALF_SIM if native.is_component_tick_enabled() and mesh.get_anim_instance() else mode.PHYSICAL

def transition(next_mode):
    previous = active_mode()
    before = body_states()
    # Python keeps the pre-Live-Coding enum wrapper. KE calls the current reflected
    # UFUNCTION with its real enum, exactly as the new Blueprint node does.
    unreal.SystemLibrary.execute_console_command(world,
        'ke ' + agent.get_path_name() + ' SetSimulationMode ' + next_mode)
    assert active_mode() == next_mode, 'Mode did not change'
    after = body_states()
    error = 0.
    if previous != mode.KINEMATIC and next_mode != mode.KINEMATIC:
        for bone in bones:
            error = max(error, math.dist(xyz(before[bone][0].translation), xyz(after[bone][0].translation)),
                        math.dist(xyz(before[bone][1]), xyz(after[bone][1])),
                        math.dist(xyz(before[bone][2]), xyz(after[bone][2])))
        assert error < 0.001, f'Physical transition lost body pose/velocity: {error}'
    state['transitions'].append({'from': str(previous), 'to': str(next_mode),
                                 'max_state_error': error})

def finish(error=None):
    if state['callback'] is not None:
        unreal.unregister_slate_post_tick_callback(state['callback'])
        state['callback'] = None
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({'passed': error is None, 'error': error,
        'actor': agent.get_name(), 'mesh': mesh.get_name(), 'initial_mesh_count': initial_meshes,
        'transitions': state['transitions'], 'samples': state['rows']}, indent=2))
    unreal.log('Three-mode test: ' + str(report) + ' error=' + str(error))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()

def sample(_delta):
    try:
        now = unreal.GameplayStatics.get_time_seconds(world)
        if now == state['last_time']:
            return
        state['last_time'] = now
        if state['phase'] < 0 or now - state['start'] >= 1.5:
            state['phase'] += 1
            if state['phase'] == len(phases):
                finish()
                return
            transition(phases[state['phase']])
            state['start'] = now
            return  # Native drive target allocation is deferred until its component tick.
        expected = phases[state['phase']]
        assert active_mode() == expected, 'Blueprint or another controller overwrote the mode'
        assert len(agent.get_components_by_class(unreal.SkeletalMeshComponent)) == initial_meshes
        assert agent.read_nn_future_world_pose() is not None
        assert mesh.is_simulating_physics('pelvis') == (expected != mode.KINEMATIC)
        if expected in (mode.HALF_SIM, mode.KINEMATIC):
            assert mesh.get_anim_instance() is not None
        if expected == mode.HALF_SIM:
            assert native.is_component_tick_enabled()
            assert mesh.get_collision_enabled() == unreal.CollisionEnabled.QUERY_AND_PHYSICS
            target = native.get_body_target_transform('pelvis')
            authored = agent.get_authored_body_world_target('pelvis')
            target_error = math.dist(xyz(target.translation), xyz(authored[2].translation))
            assert target_error < 0.01, f'Stale native target {target_error}cm'
        else:
            target_error = None
        values = body_states()
        assert all(math.isfinite(x) for v in values.values() for x in xyz(v[0].translation))
        state['rows'].append({'time': now, 'mode': str(expected), 'target_error_cm': target_error,
                              'pelvis_cm': xyz(values['pelvis'][0].translation)})
    except Exception:
        finish(traceback.format_exc())

agent.set_all_physical_feedback_tolerances(1000000., 360.)
agent.set_locomotion_input(unreal.Vector(0, 1, 0), True, unreal.Vector(0, 1, 0), 1., 1.)
state['callback'] = unreal.register_slate_post_tick_callback(sample)
print('Testing the existing manual pose agent through all three modes; no asset saves')
