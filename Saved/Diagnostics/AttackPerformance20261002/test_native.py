import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('NATIVE_ATTACK_PARITY; user Play preserved:',bool(ed.get_game_world()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.Attack.NativeGeometryParityAndCost')
