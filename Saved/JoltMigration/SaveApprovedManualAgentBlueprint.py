"""Save only the dirty Blueprint explicitly approved for the final package build."""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
import unreal

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
package = '/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
project = Path(unreal.Paths.project_dir()).resolve()
source = project/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
evidence = project/'Saved/JoltMigration'/('ApprovedBlueprintSave-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
evidence.mkdir(exist_ok=False)
shutil.copy2(source, evidence/source.name)
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest().upper()
before = digest(source)
asset = unreal.EditorAssetLibrary.load_asset(package)
assert asset
assert unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=True), 'Approved Blueprint save failed'
dirty_maps = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
dirty_content = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
assert package not in dirty_content, 'Approved Blueprint remains dirty'
report = {'package': package, 'saved': True, 'before_sha256': before, 'after_sha256': digest(source),
          'backup': str(evidence/source.name), 'dirty_maps_remaining': dirty_maps, 'dirty_content_remaining': dirty_content}
(evidence/'publication.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('APPROVED_BLUEPRINT_SAVE', str(evidence/'publication.json'))
print(json.dumps(report, indent=2))
