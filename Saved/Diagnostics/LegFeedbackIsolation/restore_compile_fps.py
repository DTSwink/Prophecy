import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LegFeedbackIsolation/compile_fps_restore.json'
s=json.loads(p.read_text())
if s['changed']:unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'t.MaxFPS '+str(s['max_fps']))
print('RESTORED_FPS',unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS'))
print('ALIGNMENT',unreal.SystemLibrary.get_console_variable_int_value('Prophecy.NNLowerFeedbackAlignment'))
print('PIE_ACTIVE',bool(ed.get_game_world()))
