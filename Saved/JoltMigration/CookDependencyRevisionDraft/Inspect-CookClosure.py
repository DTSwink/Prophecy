"""Read retained package-registry section and audit six R2 cooker roots.
Writes only a create-new report beside this script. Never loads UE or edits inputs.
"""
import collections, datetime, hashlib, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
INV = ROOT / 'Saved/JoltMigration/Inventory-20260909-051135/AssetManifest.json'
SNAP = ROOT / 'Saved/JoltMigration/NNCrowd-20260909-144331-647/snapshot-r2.json'
EXPECTED = 'EE378BCE8F54D2371C379C876B726BEDA2569F07AD86059E3F3CF51FF3FFA20F'
ADDED_ROOTS = [
    '/Game/Prophecy/Materials/M_ProphecyBloodVFX_Surface',
    '/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle',
    '/Game/Prophecy/BloodTexturePainting/M_BloodPaint_RuntimeTest',
    '/Game/_mygame/blood2/MI_blooddecal',
    '/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop',
    '/Game/Input/TIS_MobileControls',
]

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest().upper()

assert sha(INV) == EXPECTED
section, inside, closed = [], False, False
with INV.open(encoding='utf-8-sig') as f:
    for line in f:
        if not inside:
            if line.strip() == '"packages": [':
                inside = True
                section.append('[\n')
            continue
        if line.rstrip('\r\n') == '\t],':
            section.append(']\n')
            closed = True
            break
        section.append(line)
assert closed
nodes = {n['package']: n for n in json.loads(''.join(section))}
snapshot = json.loads(SNAP.read_text(encoding='utf-8-sig'))
queue = collections.deque(snapshot['gamePackageRoots'] + ADDED_ROOTS)
seen, game, external, missing_nodes, edges = set(), [], [], [], []
while queue:
    name = queue.popleft()
    if name in seen or name.startswith('/Script/'):
        continue
    seen.add(name)
    node = nodes.get(name)
    if name.startswith('/Game/'):
        game.append(name)
    else:
        external.append(name)
    if not node or not node['registryDependencyNodeAvailable']:
        missing_nodes.append(name)
        continue
    for dep in node['packageDependencies']:
        if dep.get('package'):
            edges.append(dict(source=name, **dep))
            queue.append(dep['package'])

inventory_ns = INV.stat().st_mtime_ns
old_files = {i['relativePath'] for i in snapshot['inputs']}
files, missing_files, newer_files = [], [], []
for name in sorted(game):
    stem = 'Content/' + name[6:]
    mains = [stem + suffix for suffix in ('.uasset', '.umap') if (ROOT / (stem + suffix)).is_file()]
    if len(mains) != 1:
        missing_files.append({'package': name, 'mains': mains})
        continue
    for rel in mains + [stem + suffix for suffix in ('.uexp', '.ubulk', '.uptnl')]:
        p = ROOT / rel
        if not p.is_file():
            continue
        s = p.stat()
        if s.st_mtime_ns > inventory_ns:
            newer_files.append(rel)
        files.append({'package': name, 'relativePath': rel, 'source': str(p), 'bytes': s.st_size,
                      'sourceLastWriteUtc': datetime.datetime.fromtimestamp(s.st_mtime, datetime.timezone.utc).isoformat(),
                      'sourceSha256': sha(p), 'alreadyFrozen': rel in old_files})
report = {
    'kind': 'ProphecyCookDependencyClosureAudit', 'schema': 1,
    'createdUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'predecessor': str(SNAP), 'predecessorSha256': sha(SNAP),
    'inventory': str(INV), 'inventorySha256': EXPECTED,
    'inventoryLastWriteUtc': datetime.datetime.fromtimestamp(INV.stat().st_mtime, datetime.timezone.utc).isoformat(),
    'addedRoots': ADDED_ROOTS, 'roots': snapshot['gamePackageRoots'] + ADDED_ROOTS,
    'gamePackageClosure': sorted(game), 'externalPackageClosure': sorted(external),
    'missingRegistryNodes': sorted(missing_nodes), 'missingSourcePackages': missing_files,
    'sourceFilesNewerThanInventory': newer_files, 'files': files,
    'additionalFiles': len([f for f in files if not f['alreadyFrozen']]),
    'additionalBytes': sum(f['bytes'] for f in files if not f['alreadyFrozen']),
    'allGamePackageBytes': sum(f['bytes'] for f in files), 'dependencyEdges': edges,
    'limitations': 'Inventory contains package dependency metadata, not source file hashes. Fresh source hashes are recorded here; timestamps no later than retained inventory support freshness but do not prove historical byte identity. External engine/plugin roots require separate mount and cook review.'
}
out = pathlib.Path(__file__).with_name('CookDependencyClosure.json')
with out.open('x', encoding='utf-8', newline='\n') as f:
    json.dump(report, f, indent=2)
print(json.dumps({k: v for k,v in report.items() if k not in ('files', 'dependencyEdges')}, indent=2))
