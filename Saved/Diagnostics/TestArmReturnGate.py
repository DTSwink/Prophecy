import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary:SetAttackArmReturnEnabled')
assert fn, 'Reflected Blueprint function missing'
print('ARM_RETURN_GATE_REFLECTED',fn.get_path_name())
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.SlashReturn.PerAttackGate')
print('ARM_RETURN_GATE_TEST_REQUESTED')
