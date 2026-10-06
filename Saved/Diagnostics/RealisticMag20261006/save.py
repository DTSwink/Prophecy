import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RealisticMag20261006'
d={'play':ed.get_game_world() is not None,'content':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],'maps':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
assert unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True),'Could not save current editor work'
d['remaining_content']=[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()];d['remaining_maps']=[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
(p/'push-save.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))