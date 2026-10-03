import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
    'Automation RunTests Prophecy.Jolt.Sword.AttackCollisionPhases+Prophecy.Jolt.Collision.SelfCollisionLayersAtomic')
print('ATTACK_BODY_COLLISION_TESTS_REQUESTED')
