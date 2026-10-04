import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
content=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
maps=unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
packages=list(content)+list(maps)
before=[p.get_name() for p in packages]
assert not any('/Temp/' in p or 'UEDPIE_' in p for p in before),'Refuse to save transient Play packages'
saved=unreal.EditorLoadingAndSavingUtils.save_packages(packages,True) if packages else True
result={'play':ed.get_game_world() is not None,'dirtyBefore':before,'saved':saved,'dirtyAfter':[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]+[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
path=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashLDProfile20261004/milestone-editor.json'
path.write_text(json.dumps(result,indent=2));print(json.dumps(result))
assert saved and not result['dirtyAfter']
