import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
names=['WristAttackStrengths','WristSplit','WristTwistRecoil']
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests '+'+'.join('Prophecy.Physics.ArmCone.'+n for n in names))
print('Requested three focused per-attack wrist checks')
