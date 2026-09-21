import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
 'Automation RunTests Prophecy.Jolt.SpecialSolver.Lifecycle')
