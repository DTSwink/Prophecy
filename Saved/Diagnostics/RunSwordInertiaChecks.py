import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Jolt.SwordFixture C:/Users/singerie/AppData/Local/Temp/ProphecySwordInertia-20260913.json')
