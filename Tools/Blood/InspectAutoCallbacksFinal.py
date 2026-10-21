"""Read-only post-build/editor preservation checks."""
import hashlib, json, pathlib, unreal
root = pathlib.Path(unreal.Paths.project_dir()).resolve()
out = root / "Saved/Diagnostics/BloodAutoCallbacks"
receipt = json.loads((out / "preservation.json").read_text(encoding="utf-8"))
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
result = {
    "world": ed.get_editor_world().get_path_name(),
    "play": bool(ed.get_game_world()),
    "dirty": [p.get_path_name() for p in
              unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() +
              unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
    "preserved": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
                  for name, digest in receipt["hashes"].items()},
}
unreal.SystemLibrary.execute_console_command(
    ed.get_editor_world(), "Prophecy.Editor.LiveAgentTypes Inspect")
(out / "final-state.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
