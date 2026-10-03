import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.GhostLocoDrag+Prophecy.NN.AttackEntry.FootLocomotion+Prophecy.NN.AttackEntry.PelvisRegression')
