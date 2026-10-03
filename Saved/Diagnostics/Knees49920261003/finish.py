import unreal,json,pathlib
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
r={'world':str(e.get_game_world()),'cvars':{n:unreal.SystemLibrary.get_console_variable_int_value(n) for n in ('Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames','Prophecy.Tempering.PoleTrace')}}
print(r)
pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/Knees49920261003/final-status.json').write_text(json.dumps(r))
