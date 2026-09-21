import builtins, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
if not hasattr(builtins,'_pelvis_build_fps'):
    builtins._pelvis_build_fps=unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'t.MaxFPS 5')
print('Temporary idle editor cap; original',builtins._pelvis_build_fps)
