import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
current=unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
assert current==60.,current
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'t.MaxFPS 10')
print('Temporarily reduced idle editor FPS from 60 to 10; restore to 60 before testing.')
