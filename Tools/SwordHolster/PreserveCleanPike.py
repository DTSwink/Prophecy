"""Save current user edits and close cleanly for the clean-pike native-state build."""
import hashlib, json, pathlib, shutil, unreal

root = pathlib.Path(unreal.Paths.project_dir()).resolve()
out = root / "Saved/Diagnostics/CleanPike"
out.mkdir(parents=True, exist_ok=True)
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
world = ed.get_editor_world()
content = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
maps = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
dirty = content + maps
files = []
for package in dirty:
    name = package.get_path_name()
    assert name.startswith("/Game/"), name
    path = root / "Content" / (name[6:] + (".umap" if package in maps else ".uasset"))
    backup = out / "before-restart" / path.relative_to(root / "Content")
    backup.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    files.append(path)
if dirty:
    assert unreal.EditorLoadingAndSavingUtils.save_packages(dirty, False), "Save failed"
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
receipt = {
    "world": world.get_path_name(),
    "saved": [p.get_path_name() for p in dirty],
    "hashes": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
}
(out / "preservation.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print("USER_WORK_SAVED", json.dumps(receipt))
unreal.SystemLibrary.execute_console_command(world, "CLOSE_SLATE_MAINFRAME")
