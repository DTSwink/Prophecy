import unreal
import sys

subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if subsystem.get_game_world():
    raise RuntimeError('Stop PIE before running the isolated backend checks.')
world = subsystem.get_editor_world()
unreal.SystemLibrary.execute_console_command(
    world, 'Automation RunTests ' + (sys.argv[1] if len(sys.argv) > 1 else
        'Prophecy.Jolt.BodyComponent.CharacterRuntimeChannels+Prophecy.Jolt.Character.BackendPreferenceAcrossModes'))
print('Requested isolated backend mode checks; no level or Blueprint saves.')
