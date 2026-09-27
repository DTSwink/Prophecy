import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyGhostAttackLibrary'))
assert api.call_method('GetTicksSinceLastAttack',args=(None,))==0
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.AttackControls.EntryMagicAndTicks+Prophecy.NN.AttackControls.RecoveryAndArmedGate')
print('ATTACK_TICK_GETTER_REFLECTED')
