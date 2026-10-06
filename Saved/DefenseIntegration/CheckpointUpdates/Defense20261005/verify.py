import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve existing Play session'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.Defense.CheckpointUpdate20261005+Prophecy.NN.Defense.GeometryReference+Prophecy.NN.Defense.NeuralReference')
print('DEFENSE_CHECKPOINT_TESTS_REQUESTED')
