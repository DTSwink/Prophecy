import json
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
result = {'world': world.get_path_name() if world else None, 'actors': []}
if not world:
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    result['editor_world'] = world.get_path_name() if world else None
if world:
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
        entry = {'name': actor.get_name(), 'path': actor.get_path_name(),
                 'location': str(actor.get_actor_location()),
                 'jolt': actor.is_jolt_physical_animation_enabled(),
                 'mode': str(actor.get_simulation_mode()),
                 'locomotion': str(actor.get_locomotion_state()),
                 'body': str(actor.get_physical_body_state('pelvis')),
                 'components': [(c.get_name(), c.get_class().get_name()) for c in actor.get_components_by_class(unreal.ActorComponent)]}
        entry['pose_api'] = str(actor.read_nn_future_world_pose())[:1200]
        entry['feedback_api'] = [n for n in dir(actor) if 'feedback' in n or 'magnetization' in n]
        entry['settings'] = {}
        for n in ['physical_feedback_tolerances', 'body_magnetization_settings', 'locomotion_input', 'use_blueprint_locomotion_input', 'show_kinematic_debug_mesh']:
            try:
                entry['settings'][n] = str(actor.get_editor_property(n))
            except Exception as e:
                entry['settings'][n] = str(e)
        entry['docs'] = {n: getattr(actor, n).__doc__ for n in ['get_physical_body_state', 'read_nn_future_world_pose', 'get_locomotion_state', 'get_locomotion_target', 'get_jolt_body_pair_self_collision_enabled']}
        result['actors'].append(entry)
print(json.dumps(result, indent=2))
