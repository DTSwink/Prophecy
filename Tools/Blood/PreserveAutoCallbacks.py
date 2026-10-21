"""Preserve the live user scene before the callback service's normal build."""
import hashlib, json, pathlib, shutil, unreal
root = pathlib.Path(unreal.Paths.project_dir()).resolve()
out = root / "Saved/Diagnostics/BloodAutoCallbacks"
out.mkdir(parents=True, exist_ok=True)
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
assert ed.get_editor_world().get_path_name() == "/Game/explosionVFX.explosionVFX"
dirty = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() + unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
allowed = {"/Game/explosionVFX", "/Game/_mygame/blood2/NS_bloodsplat"}
assert all(p.get_path_name() in allowed for p in dirty), [p.get_path_name() for p in dirty]
files = [root / "Content/explosionVFX.umap",
         root / "Content/_mygame/blood2/NS_bloodsplat.uasset",
         root / "Content/_mygame/blood2/A_DecalManager.uasset",
         root / "Content/_mygame/sword/A_Sword.uasset"]
for p in files[:2]:
    backup = out / (p.stem + ".before" + p.suffix)
    if p.exists() and not backup.exists():
        shutil.copy2(p, backup)
if dirty:
    assert unreal.EditorLoadingAndSavingUtils.save_packages(dirty, False)
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
receipt = {"saved": [p.get_path_name() for p in dirty],
           "hashes": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
(out / "preservation.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "CLOSE_SLATE_MAINFRAME")
