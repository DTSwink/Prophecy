import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
state=dict(pie=bool(ed.get_game_world()),dirty_content=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],dirty_maps=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
print(json.dumps(state))
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/DodgeMismatch/final_state.json').write_text(json.dumps(state))
