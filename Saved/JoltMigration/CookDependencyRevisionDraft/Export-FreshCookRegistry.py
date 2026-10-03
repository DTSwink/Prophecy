"""Run inside original project's UE PythonScript commandlet; registry-only export.
Force-rescan exactly each reached package file. No asset load, save, or mutation.
Create-new report only; all source files are hashed before and after the traversal.
"""
import collections
import datetime
import hashlib
import json
import os
import pathlib
import unreal

ROOTS = [
    '/Game/_mygame/SKM_UEFN_Mannequin',
    '/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin',
    '/Game/Prophecy/Materials/M_ProphecyBloodVFX_Surface',
    '/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle',
    '/Game/Prophecy/BloodTexturePainting/M_BloodPaint_RuntimeTest',
    '/Game/_mygame/blood2/MI_blooddecal',
    '/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop',
    '/Game/Input/TIS_MobileControls',
]
if os.environ.get('PROPHECY_COOK_REGISTRY_ROOTS_JSON'):
    ROOTS = json.loads(os.environ['PROPHECY_COOK_REGISTRY_ROOTS_JSON'])
    if not isinstance(ROOTS, list) or not ROOTS or not all(isinstance(root, str) and root.startswith('/') for root in ROOTS):
        raise RuntimeError('Explicit cook registry roots must be a nonempty package-name list')
OUT = pathlib.Path(os.environ.get('PROPHECY_COOK_REGISTRY_OUTPUT', str(pathlib.Path(__file__).with_name('FreshCookRegistry.json')))).resolve()
if OUT.exists():
    raise RuntimeError('Refusing to overwrite report: ' + str(OUT))
OUT.parent.mkdir(parents=True, exist_ok=True)

def absolute(s):
    return pathlib.Path(unreal.Paths.convert_relative_path_to_full(s)).resolve()

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest().upper()

mounts = {'/Game/': absolute(unreal.Paths.project_content_dir()), '/Engine/': absolute(unreal.Paths.engine_content_dir())}
for plugin in unreal.PluginBlueprintLibrary.get_enabled_plugin_names():
    mount = unreal.PluginBlueprintLibrary.get_plugin_mounted_asset_path(plugin)
    content = unreal.PluginBlueprintLibrary.get_plugin_content_dir(plugin)
    if mount and content:
        key = str(mount).rstrip('/') + '/'
        path = absolute(content)
        if key in mounts and mounts[key] != path:
            raise RuntimeError('Conflicting mounted content path: ' + key)
        mounts[key] = path

registry = unreal.AssetRegistryHelpers.get_asset_registry()
queries = []
for game in (True, False):
    for hard in (True, False):
        options = unreal.AssetRegistryDependencyOptions()
        options.include_hard_package_references = hard
        options.include_soft_package_references = not hard
        options.include_game_package_references = game
        options.include_editor_only_package_references = not game
        options.include_searchable_names = False
        options.include_hard_management_references = False
        options.include_soft_management_references = False
        queries.append((game, hard, options))

queue = collections.deque(ROOTS)
seen, nodes, source_files = set(), [], {}
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
while queue:
    name = queue.popleft()
    if name in seen or name.startswith('/Script/'):
        continue
    seen.add(name)
    if len(seen) > 5000:
        raise RuntimeError('Bounded export exceeded 5000 reached non-script packages')
    matching_mounts = [m for m in mounts if name.startswith(m)]
    if len(matching_mounts) != 1:
        raise RuntimeError('Expected one enabled mount for ' + name)
    mount = matching_mounts[0]
    stem = mounts[mount] / name[len(mount):]
    mains = [pathlib.Path(str(stem) + ext) for ext in ('.uasset', '.umap') if pathlib.Path(str(stem) + ext).is_file()]
    if len(mains) != 1:
        raise RuntimeError('Expected one on-disk package for ' + name + ': ' + str(mains))
    files = mains + [pathlib.Path(str(stem) + ext) for ext in ('.uexp', '.ubulk', '.uptnl') if pathlib.Path(str(stem) + ext).is_file()]
    for path in files:
        s = path.stat()
        source_files[str(path)] = {'path': str(path), 'package': name, 'bytes': s.st_size,
                                  'lastWriteUtc': datetime.datetime.fromtimestamp(s.st_mtime, datetime.timezone.utc).isoformat(),
                                  'lastWriteNs': s.st_mtime_ns, 'sha256': sha(path)}
    registry.scan_files_synchronous([str(mains[0])], True)
    assets = registry.get_assets_by_package_name(name, True)
    if not assets:
        raise RuntimeError('Fresh scan returned no on-disk asset metadata for ' + name)
    dependencies = []
    for game, hard, options in queries:
        result = registry.get_dependencies(name, options)
        if result is None:
            raise RuntimeError('Fresh scan has no dependency node for ' + name)
        for dep in sorted(str(v) for v in result):
            dependencies.append({'package': dep, 'hard': hard, 'game': game})
            queue.append(dep)
    nodes.append({'package': name, 'registryDependencyNodeAvailable': True,
                  'assets': [{'assetName': str(a.asset_name), 'packageName': str(a.package_name), 'classPath': str(a.asset_class_path)} for a in assets],
                  'packageDependencies': dependencies})

for row in source_files.values():
    path = pathlib.Path(row['path'])
    if sha(path) != row['sha256'] or path.stat().st_mtime_ns != row['lastWriteNs']:
        raise RuntimeError('Source package changed while export was reading: ' + str(path))

by_name = {n['package']: n for n in nodes}
runtime, pending = set(), collections.deque(ROOTS)
while pending:
    name = pending.popleft()
    if name in runtime or name.startswith('/Script/'):
        continue
    runtime.add(name)
    pending.extend(e['package'] for e in by_name[name]['packageDependencies'] if e['game'])

report = {'kind': 'ProphecyFreshCookRegistry', 'schema': 1, 'success': True,
          'startedUtc': started, 'completedUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'engineVersion': unreal.SystemLibrary.get_engine_version(), 'projectDirectory': str(absolute(unreal.Paths.project_dir())),
          'rootPackages': ROOTS, 'packageCount': len(nodes), 'gamePackageClosure': sorted(n for n in seen if n.startswith('/Game/')),
          'runtimeGamePackageClosure': sorted(n for n in runtime if n.startswith('/Game/')),
          'externalPackageClosure': sorted(n for n in seen if not n.startswith('/Game/')),
          'runtimeExternalPackageClosure': sorted(n for n in runtime if not n.startswith('/Game/')),
          'mounts': {k: str(v) for k,v in mounts.items()}, 'packages': sorted(nodes, key=lambda n:n['package']),
          'files': sorted(source_files.values(), key=lambda n:n['path']), 'sourceHashesAndTimestampsUnchanged': True,
          'assetsLoadedOrSavedByExporter': False,
          'coverage': 'Fresh force-rescan of each reached on-disk package only; complete hard/soft package graph with separate game/editor-only edge queries, excluding management/searchable-name categories. /Script dependencies are recorded edges but not scanned as content.',
          'limitations': 'No dynamic-string/config references inferred beyond the eight reviewed roots. Exporter does not suppress engine startup work. Runtime-only closure is a separately reported subset; full closure remains available and no cooking policy is changed.'}
with OUT.open('x', encoding='utf-8', newline='\n') as f:
    json.dump(report, f, indent=2)
unreal.log('PROPHECY_FRESH_COOK_REGISTRY_COMPLETE ' + str(OUT) + ' packages=' + str(len(nodes)))
