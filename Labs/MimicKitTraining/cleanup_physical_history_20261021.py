"""One-time user-authorized cleanup; preserve both verified branch checkpoints."""
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from botocore.config import Config
import deploy_limp_floor as d

OUT = d.ROOT / 'Saved/MimicKitEquipment/cleanup-20261021'

def main():
    protected = json.loads((OUT / 'preserved.json').read_text())
    keep_keys = {r['key'] for r in protected}
    keep_local = {Path(r['local']).resolve() for r in protected}
    client = boto3.client('s3', **d.cloud.credentials(), config=Config(
        connect_timeout=10, read_timeout=60, retries={'max_attempts': 3}))
    for r in protected:
        path = Path(r['local'])
        assert path.stat().st_size == r['bytes']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == r['sha256']
        current = json.loads(client.get_object(Bucket=d.cloud.rp.VOLUME_ID,
            Key=r['key'].rsplit('/', 1)[0] + '/latest_verified.json')['Body'].read())
        assert current['key'] == r['key'], 'Latest changed; re-download before cleanup'
        assert current['sha256'] == r['sha256']

    plan = json.loads((OUT / 'deletion-plan.json').read_text())
    for r in plan:
        k = r['key']
        assert k.startswith('mimickit/pipeline_20261014/') and k not in keep_keys
        assert ('/equipment/' in k or ('/runs/' in k and '_uefn_' in k and '_crawl_' not in k))
        assert Path(k).name.startswith(('checkpoint_', 'preserved_checkpoint_', 'rollout_step_')) or Path(k).name in ('replay.npz', 'rollout.json')

    # Do not touch datasets, source archives, TB files, or other Unreal models.
    local = set()
    roots = [(d.ROOT / 'Saved/MimicKitEquipment').resolve(),
             (d.ROOT / 'Saved/MimicKitLocomotion').resolve()]
    runroot = Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs').resolve()
    for root in roots:
        for p in root.rglob('*'):
            if p.is_file() and 'checkpoint' in p.name.lower() and p.suffix in ('.zip', '.pt', '.pth'):
                local.add(p.resolve())
    for run in runroot.glob('mimickit_*uefn_*'):
        if not run.is_dir() or '_crawl_' in run.name:
            continue
        for p in run.rglob('*'):
            if p.is_file() and (p.name.startswith(('checkpoint_', 'rollout_step_')) or p.name in ('replay.npz', 'rollout.json')):
                local.add(p.resolve())
    local -= keep_local
    local_plan = []
    for p in sorted(local):
        assert any(p.is_relative_to(r) for r in roots + [runroot])
        assert not p.is_symlink()
        local_plan.append({'path': str(p), 'bytes': p.stat().st_size})
    (OUT / 'local-deletion-plan.json').write_text(json.dumps(local_plan, indent=2))

    with (OUT / 'deletion-receipts.jsonl').open('a') as log:
        for start in range(0, len(plan), 200):
            batch = plan[start:start + 200]
            # This Runpod S3 endpoint redirects unsupported DeleteObjects.
            def remove(row):
                result = client.delete_object(Bucket=d.cloud.rp.VOLUME_ID, Key=row['key'])
                return {'key': row['key'], 'http_status': result['ResponseMetadata']['HTTPStatusCode']}
            with ThreadPoolExecutor(max_workers=8) as pool:
                for result in pool.map(remove, batch):
                    log.write(json.dumps({'time': time.time(), **result}) + '\n'); log.flush()
            print('Deleted persistent objects', start + len(batch), '/', len(plan), flush=True)
        remaining = set()
        for page in client.get_paginator('list_objects_v2').paginate(
                Bucket=d.cloud.rp.VOLUME_ID, Prefix='mimickit/pipeline_20261014/'):
            remaining.update(x['Key'] for x in page.get('Contents', []))
        assert not remaining.intersection(r['key'] for r in plan)
        assert keep_keys.issubset(remaining)
        for row in local_plan:
            p = Path(row['path'])
            assert p not in keep_local and p.stat().st_size == row['bytes']
            p.unlink()
        assert all(not Path(r['path']).exists() for r in local_plan)
    # Prove full checkpoint-sized backups work again, including readback.
    from backup import verified_readback
    probe = 'mimickit/diagnostics/cleanup_20261021_checkpoint_write_probe.zip'
    r = max(protected, key=lambda x: x['bytes'])
    try:
        client.put_object(Bucket=d.cloud.rp.VOLUME_ID, Key=probe, Body=Path(r['local']).read_bytes())
        verified_readback(client, d.cloud.rp.VOLUME_ID, probe, r['sha256'])
    finally:
        client.delete_object(Bucket=d.cloud.rp.VOLUME_ID, Key=probe)
    receipt = dict(persistent_objects=len(plan), persistent_bytes=sum(r['bytes'] for r in plan),
        local_files=len(local_plan), local_bytes=sum(r['bytes'] for r in local_plan),
        protected=protected, checkpoint_sized_write_readback=True, completed_unix=time.time())
    (OUT / 'completed.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt), flush=True)

if __name__ == '__main__':
    main()
