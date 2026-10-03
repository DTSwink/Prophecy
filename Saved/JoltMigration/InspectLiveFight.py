"""Read-only editor/PIE inventory for the Jolt visual handoff; saves no assets."""
import json
from pathlib import Path
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
world = unreal.EditorLevelLibrary.get_game_world() if levels.is_in_play_in_editor() else editor.get_editor_world()
assert world
actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
report = {'world': world.get_path_name(), 'pie': levels.is_in_play_in_editor(), 'actor_count': len(actors),
          'agents': [], 'primitive_counts': {}, 'apis': {}}
for actor in actors:
    if isinstance(actor, unreal.ProphecyAgent):
        mesh = actor.get_pose_reference_mesh()
        report['agents'].append({'name': actor.get_name(), 'class': actor.get_class().get_path_name(),
            'location': str(actor.get_actor_location()), 'mode': str(actor.get_simulation_mode()),
            'manual': actor.get_editor_property('manual_nn_pose_application'),
            'jolt': actor.is_jolt_physical_animation_enabled(),
            'mesh': mesh.get_path_name() if mesh else None,
            'skeleton': str(mesh.get_editor_property('skeletal_mesh_asset')) if mesh else None,
            'sword': str(actor.get_held_sword())})
    for component in actor.get_components_by_class(unreal.PrimitiveComponent):
        key = str(component.get_editor_property('mobility')) + '/' + str(component.get_collision_enabled()) + '/' + component.get_class().get_name()
        report['primitive_counts'][key] = report['primitive_counts'].get(key, 0) + 1
for cls, names in [(unreal.Actor, ['add_component_by_class', 'add_instance_component']),
                   (unreal.ProphecyJoltSceneCollisionComponent, ['register_component', 'enable_scene_collision']),
                   (unreal.ProphecyJoltBlueprintLibrary, ['initialize_jolt_world']),
                   (unreal.ProphecyAgent, ['set_macd_enabled', 'enable_jolt_physical_animation'])]:
    for name in names:
        report['apis'][cls.__name__ + '.' + name] = str(getattr(cls, name).__doc__) if hasattr(cls, name) else None
target = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/LiveFightInspection.json'
target.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
