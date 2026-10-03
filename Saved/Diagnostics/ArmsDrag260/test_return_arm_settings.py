import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user PIE: the automation runner ends active play'
names=['PerArmSettings','ArmInfluence','BothArms','PerAttackGate']
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests '+'+'.join('Prophecy.NN.SlashReturn.'+n for n in names))
print('Requested four focused independent-arm return checks')
