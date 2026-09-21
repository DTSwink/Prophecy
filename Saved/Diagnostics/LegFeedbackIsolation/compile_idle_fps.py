import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
s={'max_fps':unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS'),'changed':False}
if not ed.get_game_world():
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'t.MaxFPS 10')
 s['changed']=True
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LegFeedbackIsolation/compile_fps_restore.json'
p.write_text(json.dumps(s))
print('COMPILE_EDITOR_FPS',s)
