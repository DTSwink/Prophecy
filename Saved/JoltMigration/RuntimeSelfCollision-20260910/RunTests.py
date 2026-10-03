from pathlib import Path
import unreal

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
print('Runtime self-collision verification: full Prophecy.Jolt suite requested')
unreal.SystemLibrary.execute_console_command(world, 'Automation RunTests Prophecy.Jolt')
