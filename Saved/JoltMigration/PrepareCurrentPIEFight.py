"""Prepare the fresh testNN PIE actors for the temporary Jolt visual session."""
import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world and unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
assert 'testNN' in world.get_name()
actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
for actor in actors:
    print('AGENT_READY', actor.get_name(), actor.get_actor_location(), actor.is_macd_enabled())
    for component in actor.get_components_by_class(unreal.StaticMeshComponent):
        print('AGENT_PRIMITIVE', component.get_path_name(), component.get_collision_enabled())
selected = [a for a in actors if a.get_name() == 'BP_ProphecyManualPoseAgent_C_0']
assert len(selected) == 1
# This PIE actor's BeginPlay automatically equipped its temporary sword. Re-equip
# through the visual helper so it can verify the complete native admission path.
selected[0].hide_sword()
print('TEMPORARY_PIE_SWORD_READY_FOR_NATIVE_REEQUIP')
