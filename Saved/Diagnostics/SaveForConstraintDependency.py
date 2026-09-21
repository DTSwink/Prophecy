import unreal, pathlib, shutil, json, time
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'PIE must be stopped before dependency replacement'
dirty = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
allowed = {'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent', '/Game/testNN'}
assert all(p.get_path_name() in allowed for p in dirty), [p.get_path_name() for p in dirty]
root = pathlib.Path(unreal.Paths.project_dir()).resolve()
backup = root / 'Saved/Diagnostics/ConstraintDependencyRestart' / time.strftime('%Y%m%d-%H%M%S')
backup.mkdir(parents=True, exist_ok=True)
for path in allowed:
    suffix = '.umap' if path == '/Game/testNN' else '.uasset'
    file = root / 'Content' / (path.removeprefix('/Game/') + suffix)
    shutil.copy2(file, backup / file.name)
assert unreal.EditorLoadingAndSavingUtils.save_packages(dirty, True), 'Saving current edits failed'
(backup / 'saved.json').write_text(json.dumps({'saved': [p.get_path_name() for p in dirty]}, indent=2))
print('CONSTRAINT_RESTART_SAVED', str(backup))
unreal.SystemLibrary.quit_editor()
