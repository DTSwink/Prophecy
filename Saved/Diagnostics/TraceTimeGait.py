import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
assert w
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/nn_inputs.jsonl'
offset=p.stat().st_size if p.exists() else 0
(p.parent.parent/'TimeGaitTraceOffset.json').write_text(json.dumps(dict(offset=offset)))
unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 240')
