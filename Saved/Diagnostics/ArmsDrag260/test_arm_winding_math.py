import unreal
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
# The automation framework ends PIE even for a pure-math test.
assert not e.get_game_world(),'Preserve user PIE'
unreal.SystemLibrary.execute_console_command(e.get_editor_world(),'Automation RunTests Prophecy.Physics.ArmCone.WristSplit')
print('Requested only wrist split/arm winding math')
