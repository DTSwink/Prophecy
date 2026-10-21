"""Preserve the live user map, then close cleanly for the retained-layout build."""
import hashlib, json, pathlib, shutil, unreal
root = pathlib.Path(unreal.Paths.project_dir())
out = root / "Saved/Diagnostics/BloodRectangleInstall"
out.mkdir(parents=True, exist_ok=True)
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "User Play is active; leave it untouched"
dirty = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() + unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
allowed = {"/Game/explosionVFX", "/Game/_mygame/sword/A_Sword"}
assert all(p.get_path_name() in allowed for p in dirty), [p.get_path_name() for p in dirty]
map_file = root / "Content/explosionVFX.umap"
if not (out / "explosionVFX.before.umap").exists():
    shutil.copy2(map_file, out / "explosionVFX.before.umap")
sword_file = root / "Content/_mygame/sword/A_Sword.uasset"
if not (out / "A_Sword.before.uasset").exists():
    shutil.copy2(sword_file, out / "A_Sword.before.uasset")
if dirty:
    assert unreal.EditorLoadingAndSavingUtils.save_packages(dirty, False)
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
files = [map_file, sword_file, *root.glob("Content/**/A_DecalManager.uasset")]
receipt = {"saved": [p.get_path_name() for p in dirty],
           "hashes": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.exists()}}
(out / "preservation.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "CLOSE_SLATE_MAINFRAME")
