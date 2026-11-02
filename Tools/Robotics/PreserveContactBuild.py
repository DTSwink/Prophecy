"""Save dirty user packages and close cleanly for the authorized native rebuild."""
from pathlib import Path
import hashlib
import json
import shutil
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world():
    raise RuntimeError('Preserving user Play: stop it before the native rebuild.')
root = Path(unreal.Paths.project_dir()).resolve()
out = root/'Saved/Diagnostics/RobotLocomotion20261026/contact-preservation'
out.mkdir(parents=True, exist_ok=True)
dirty = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
dirty += list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
record = dict(map=editor.get_editor_world().get_path_name(), saved=[])
files = []
for package in dirty:
    name = package.get_path_name()
    if not name.startswith('/Game/'):
        raise RuntimeError('Unexpected dirty package requires review: '+name)
    paths = [root/'Content'/(name[6:]+suffix) for suffix in ('.uasset', '.umap')]
    present = [p for p in paths if p.exists()]
    if len(present) != 1:
        raise RuntimeError('Cannot safely preserve package: '+name)
    path = present[0]
    backup = out/'before-save'/path.relative_to(root)
    if backup.exists():
        raise RuntimeError('Preservation already exists; refusing to overwrite: '+str(backup))
    files.append((name, path, backup))
for name, path, backup in files:
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
if dirty and not unreal.EditorLoadingAndSavingUtils.save_packages(dirty, False):
    raise RuntimeError('Package saving did not complete; editor stays open.')
for name, path, _ in files:
    record['saved'].append(dict(package=name, file=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
remaining = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
remaining += list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
if remaining:
    raise RuntimeError('Packages remain dirty; editor stays open.')
(out/'receipt.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record))
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'CLOSE_SLATE_MAINFRAME')
