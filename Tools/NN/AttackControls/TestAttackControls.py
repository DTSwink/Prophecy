import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
ghost=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyGhostAttackLibrary'))
pins=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary'))
assert not ghost.call_method('SetAttackArmedBlocked',args=(None,True))
assert not pins.call_method('SetAttackRecoveryRunPinningBoost',args=(None,True,.5,1.,1.))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.AttackControls.RecoveryAndArmedGate+Prophecy.NN.SpecialRecovery.RegionalOwnership+Prophecy.NN.RunPinning.HighestBoost')
print('ATTACK_CONTROL_NODES_REFLECTED_AND_CALLABLE')
