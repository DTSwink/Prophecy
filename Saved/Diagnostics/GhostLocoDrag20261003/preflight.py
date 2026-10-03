import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out=dict(play=str(ed.get_game_world()),dirty_content=[str(x.get_path_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],dirty_maps=[str(x.get_path_name()) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/GhostLocoDrag20261003'
(p/'preflight.json').write_text(json.dumps(out));print(out)
