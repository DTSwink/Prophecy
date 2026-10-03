import json
import unreal
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_game_world() if unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor() else editor.get_editor_world()
assert world
rows=[]
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if isinstance(actor, unreal.ProphecyAgent) or actor.get_class().get_name() == 'A_Sword_C':
        continue
    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        if component.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION:
            continue
        rows.append({'actor': actor.get_name(), 'class':actor.get_class().get_path_name(),
            'label':actor.get_actor_label(), 'component':component.get_name(),
            'mobility':str(component.get_editor_property('mobility')), 'simulating': component.is_simulating_physics(),
            'tick': actor.is_actor_tick_enabled(), 'transform':str(component.get_world_transform()),
            'mesh':str(component.get_editor_property('static_mesh'))})
print(json.dumps(rows, indent=2))
controller=unreal.GameplayStatics.get_player_controller(world,0) if unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor() else None
if controller: print('VIEW',controller.get_view_target())
