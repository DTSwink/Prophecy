"""Read-only final reflection, user-save preservation and editor-state check."""
import hashlib, json, pathlib, unreal

root = pathlib.Path(unreal.Paths.project_dir()).resolve()
out = root / "Saved/Diagnostics/SkeletalBloodBrush"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "Play is active"
saved = json.loads((out / "preservation.json").read_text(encoding="utf-8"))
assert all(hashlib.sha256((root / f).read_bytes()).hexdigest() == h
           for f, h in saved["hashes"].items()), "User asset changed since preservation"
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "Prophecy.Editor.LiveAgentTypes Inspect")
result = {
    "world": ed.get_editor_world().get_path_name(),
    "play": False,
    "preserved_user_asset_hashes": True,
    "dirty": [p.get_path_name() for p in
              unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
              + unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
}
(out / "editor-final.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
