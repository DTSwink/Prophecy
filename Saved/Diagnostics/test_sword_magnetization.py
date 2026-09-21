import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
cls = unreal.load_class(None, '/Script/GameAnimationSample3.ProphecySwordPhysicsLibrary')
assert cls
lib = unreal.get_default_object(cls)
assert lib.call_method('BreakSwordGripConstraint', (None,)) is False
assert unreal.load_class(None, '/Script/ProphecyJolt.ProphecyJoltBodyDriveLibrary')
print('SWORD_DRIVE_NODES_LOADED; PIE preserved:', bool(ed.get_game_world()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Automation RunTests Prophecy.Jolt.Sword.IndependentHandMagnetization+Prophecy.Jolt.Sword.AttackCollisionPhases')
