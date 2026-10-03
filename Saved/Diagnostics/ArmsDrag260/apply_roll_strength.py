import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RefreshArmConeTwist')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.SetWristRecoilTuning K2Node_CallFunction_277 15 75 20 300')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
print('Refreshed roll pin and set roll300; pointing75/damping20/limit15; unsaved')
