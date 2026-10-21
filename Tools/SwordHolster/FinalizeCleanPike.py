"""Save the verified pike edit, preserve prior bytes, and inspect native reflection."""
import hashlib, json, pathlib, shutil, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'User Play left untouched'
root = pathlib.Path(unreal.Paths.project_dir())
out = root / 'Saved/Diagnostics/CleanPike'
check = json.loads((out / 'graph-check.json').read_text())
play = json.loads((out / 'play.json').read_text())
assert check['conditions_and_tuning_preserved'] and check['joint_pins_preserved']
assert not play['error'] and play['first_cut']
assert play['first_cut']['velocity'] == play['first_cut']['incoming_velocity']
asset = root / 'Content/_mygame/sword/A_Sword.uasset'
backup = out / 'before-restart/A_Sword.uasset'
if not backup.exists(): shutil.copy2(asset, backup)
bp = unreal.load_asset('/Game/_mygame/sword/A_Sword')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
check['saved'] = True
check['before_sha256'] = hashlib.sha256(backup.read_bytes()).hexdigest()
check['after_sha256'] = hashlib.sha256(asset.read_bytes()).hexdigest()
(out / 'graph-check.json').write_text(json.dumps(check, indent=2))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes Inspect')
result = {
    'world': ed.get_editor_world().get_path_name(),
    'play': bool(ed.get_game_world()),
    'dirty': [x.get_path_name() for x in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
              + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())],
    'map_sha256': hashlib.sha256((root / 'Content/explosionVFX.umap').read_bytes()).hexdigest(),
    'first_cut': play['first_cut'], 'saved': True,
}
(out / 'verification.json').write_text(json.dumps(result, indent=2))
unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([bp])
print(json.dumps(result))
