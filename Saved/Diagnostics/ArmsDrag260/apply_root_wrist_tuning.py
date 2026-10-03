import unreal,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
values=list(map(float,sys.argv[1:])) if len(sys.argv)>1 else [15.,100.,20.]
assert len(values)==3
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.SetWristRecoilTuning K2Node_CallFunction_277 '+' '.join(map(str,values)))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
print('Applied root-wrist tuning request; inspect compile status and pin audit; no asset save')
