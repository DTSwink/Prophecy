"""Back up the exact library before the isolated packaging repair; no asset writes."""
import hashlib
import json
import shutil
from pathlib import Path
import unreal

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
root = Path(unreal.Paths.project_dir()).resolve()
output = root / 'Saved/JoltMigration/AngSpringRepair-20260910'
output.mkdir(exist_ok=False)
source = root / 'Content/_mygame/NewFunctionLibrary.uasset'
before_hash = hashlib.sha256(source.read_bytes()).hexdigest()
backup = output / 'NewFunctionLibrary.uasset.original'
shutil.copy2(source, backup)
assert hashlib.sha256(backup.read_bytes()).hexdigest() == before_hash
report = {'asset': '/Game/_mygame/NewFunctionLibrary', 'source': str(source),
          'backup': str(backup), 'before_sha256': before_hash, 'before_bytes': source.stat().st_size}
(output / 'backup.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
