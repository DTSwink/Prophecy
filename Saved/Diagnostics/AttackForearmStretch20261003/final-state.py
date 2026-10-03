import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out=dict(world=ed.get_editor_world().get_path_name(),play=str(ed.get_game_world()),
 dirty_content=[x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
 dirty_maps=[x.get_path_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
assert ed.get_game_world() is None
assert not out['dirty_content'] and not out['dirty_maps'],out
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackForearmStretch20261003/final-state.json').write_text(json.dumps(out))
print(out)
