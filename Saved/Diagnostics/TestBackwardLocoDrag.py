import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
# Isolated native test world; never starts/stops or modifies user PIE.
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.AttackEntry.FootLocomotion')
print('BACKWARD_LOCO_DRAG_FOCUSED_TEST_REQUESTED')
