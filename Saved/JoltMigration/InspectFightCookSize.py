"""Read the cached runtime dependency graph for final-package sizing; no asset loads/saves."""
import collections
import json
from datetime import datetime
from pathlib import Path
import unreal

roots = ['/Game/testNN', '/Game/_mygame/sword/A_Sword',
         '/Game/_mygame/sword/geometry/Sword_GL01_Training',
         '/Game/_mygame/SKM_UEFN_Mannequin',
         '/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin',
         '/Engine/BasicShapes/Cube']
mounts = {'/Game/': Path(unreal.Paths.project_content_dir()).resolve(),
          '/Engine/': Path(unreal.Paths.engine_content_dir()).resolve()}
for plugin in unreal.PluginBlueprintLibrary.get_enabled_plugin_names():
    mount = unreal.PluginBlueprintLibrary.get_plugin_mounted_asset_path(plugin)
    content = unreal.PluginBlueprintLibrary.get_plugin_content_dir(plugin)
    if mount and content:
        mounts[str(mount).rstrip('/')+'/'] = Path(content).resolve()
options = unreal.AssetRegistryDependencyOptions()
options.include_hard_package_references = True
options.include_soft_package_references = True
options.include_game_package_references = True
options.include_editor_only_package_references = False
options.include_searchable_names = False
options.include_hard_management_references = False
options.include_soft_management_references = False
registry = unreal.AssetRegistryHelpers.get_asset_registry()
seen, files, missing = set(), [], []
pending = collections.deque(roots)
while pending:
    name = pending.popleft()
    if name in seen or name.startswith('/Script/'):
        continue
    seen.add(name)
    assert len(seen) <= 10000, 'Dependency sizing exceeded 10000 packages'
    matches = [m for m in mounts if name.startswith(m)]
    found = []
    if len(matches) == 1:
        stem = mounts[matches[0]] / name[len(matches[0]):]
        found = [Path(str(stem)+ext) for ext in ('.uasset','.umap','.uexp','.ubulk','.uptnl') if Path(str(stem)+ext).is_file()]
    if not found:
        missing.append(name)
    files.extend({'package': name, 'path': str(p), 'bytes': p.stat().st_size} for p in found)
    pending.extend(str(n) for n in (registry.get_dependencies(name, options) or []))
report = {'roots': roots, 'package_count': len(seen), 'source_bytes': sum(f['bytes'] for f in files),
          'missing_packages': sorted(missing), 'files': sorted(files, key=lambda f: -f['bytes']),
          'scope': 'Cached runtime hard/soft registry closure and on-disk source sizes; not cooked sizes or a fresh closure guarantee.'}
target = Path(unreal.Paths.project_saved_dir()).resolve()/'JoltMigration'/('FightCookSize-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
target.write_text(json.dumps(report, indent=2), encoding='utf-8')
print('FIGHT_COOK_SIZE', str(target))
print(json.dumps({k:v for k,v in report.items() if k != 'files'}, indent=2))
print('LARGEST_SOURCE_PACKAGES', json.dumps(report['files'][:10], indent=2))
