"""Save only the library after the isolated parameter repair passes its checks."""
import hashlib
import json
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
output = root / 'Saved/JoltMigration/AngSpringRepair-20260910'
backup = json.loads((output / 'backup.json').read_text(encoding='utf-8'))
repair = json.loads((output / 'repair.json').read_text(encoding='utf-8'))
assert repair['success'] and repair['compile_errors'] == 0
assert repair['remaining_pins_and_wires_unchanged'] and repair['generated_context_pin_verified']
assert not repair['asset_saved']
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
dirty = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
assert dirty == ['/Game/_mygame/NewFunctionLibrary'], dirty
source = Path(backup['source'])
assert hashlib.sha256(source.read_bytes()).hexdigest() == backup['before_sha256']
asset = unreal.load_asset('/Game/_mygame/NewFunctionLibrary')
assert unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=True)
report = dict(backup)
report.update(after_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), after_bytes=source.stat().st_size,
              dirty_maps=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
              dirty_content=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()])
(output / 'publication.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
assert not report['dirty_maps'] and not report['dirty_content']
print(json.dumps(report, indent=2))
