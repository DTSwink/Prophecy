import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
names=('Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames','Prophecy.NNInputTraceFrames')
result=dict(play_world=str(ed.get_game_world()),editor_world=str(ed.get_editor_world()),cvars={n:unreal.SystemLibrary.get_console_variable_int_value(n) for n in names})
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/HeadSwingAudit20261003'
(p/'restored.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
