import unreal

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
cls = unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyAttackRecoveryLibrary')
assert cls, 'Attack recovery Blueprint library was not loaded'
lib = unreal.get_default_object(cls)
assert lib.call_method('SetAttackToLocomotionBlend', (None, 1.0)) is False
print('ATTACK_RECOVERY_NODE_LOADED; PIE preserved:', bool(ed.get_game_world()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Automation RunTests Prophecy.NN.PolicyBlend')
