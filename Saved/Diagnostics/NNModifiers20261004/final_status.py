import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
r=dict(play=w is not None,map=ed.get_editor_world().get_name(),trace_agent=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.SlashTraceAgent'),trace_frames=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.SlashTraceFrames'),node=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNModifierDebugLibrary').get_path_name())
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/NNModifiers20261004'
(p/'final-status.json').write_text(json.dumps(r,indent=2))
print(json.dumps(r))
