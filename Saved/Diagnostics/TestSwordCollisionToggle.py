import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecySwordPhysicsLibrary:SetSwordCollisionEnabled')
assert fn, 'Sword collision node not reflected'
print('SWORD_COLLISION_NODE',fn.get_path_name())
assert not ed.get_game_world(), 'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Jolt.Sword.AttackCollisionPhases')
print('SWORD_COLLISION_TEST_REQUESTED')
