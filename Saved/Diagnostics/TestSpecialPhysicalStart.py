import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecySpecialStartLibrary:SetSpecialStartFromPhysical')
assert fn, 'Special start node not reflected'
print('SPECIAL_PHYSICAL_START_NODE',fn.get_path_name())
assert not ed.get_game_world(), 'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Jolt.Special.PhysicalStart')
print('SPECIAL_PHYSICAL_START_TEST_REQUESTED')
