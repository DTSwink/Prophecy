import unreal, pathlib, shutil, json, hashlib, time
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world(), 'Stop PIE before saving current edits'
dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
expected='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
assert all(p.get_path_name()==expected for p in dirty), 'Unexpected unsaved packages; preserve them before restart: '+str([p.get_path_name() for p in dirty])
root=pathlib.Path(unreal.Paths.project_dir())
backup=root/'Saved/Diagnostics/WristSnap'/('UserEditsBackup-'+time.strftime('%Y%m%d-%H%M%S'))
rows=[]
for package in dirty:
    path=root/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
    backup.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,backup/path.name)
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    bp=unreal.load_asset(expected)
    assert bp
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=True)
    after=hashlib.sha256(path.read_bytes()).hexdigest()
    shutil.copy2(path,backup/('Current-'+path.name))
    rows.append(dict(asset=expected,before_sha256=before,after_sha256=after))
if rows:(backup/'record.json').write_text(json.dumps(rows,indent=2))
print('PRESERVED_CURRENT_USER_EDITS',str(backup),rows)

