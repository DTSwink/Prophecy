"""Resume the existing PIE visual check without changing assets or bindings."""
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world and unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(), 'No live PIE session to resume'
if unreal.GameplayStatics.is_game_paused(world):
    assert unreal.GameplayStatics.set_game_paused(world, False), 'Unable to resume PIE'
assert not unreal.GameplayStatics.is_game_paused(world)
print('VISUAL_HANDOFF_RESUMED', world.get_path_name())
