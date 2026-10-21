"""Save only the verified sword correction and record final editor state."""
import hashlib, json, pathlib, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), "User Play left untouched"
root = pathlib.Path(unreal.Paths.project_dir()).resolve()
out = root / "Saved/Diagnostics/SceneClock"
bp = unreal.load_asset("/Game/_mygame/sword/A_Sword")
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
world = ed.get_editor_world()
# Restore the original pre-investigation editor cap, which was 60 before the crash.
unreal.SystemLibrary.execute_console_command(world, "t.MaxFPS 60")
unreal.SystemLibrary.execute_console_command(world, "Prophecy.Editor.LiveAgentTypes Inspect")
result = {
    "world": world.get_path_name(), "play": False,
    "cap": unreal.SystemLibrary.get_console_variable_float_value("t.MaxFPS"),
    "sword_sha256": hashlib.sha256((root / "Content/_mygame/sword/A_Sword.uasset").read_bytes()).hexdigest(),
    "dirty": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
              + unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
}
(out / "slow-final.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
