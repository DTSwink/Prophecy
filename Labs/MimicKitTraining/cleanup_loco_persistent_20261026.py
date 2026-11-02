"""Download/verify latest, then prune only authorized locomotion intermediates."""
import hashlib, io, json, re, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import torch
import deploy_locomotion_branch as d

OUT = d.OUT / 'checkpoint-cleanup-20261026'
PREFIX = 'mimickit/pipeline_20261014/runs/'
PATTERN = re.compile(r'^' + re.escape(PREFIX) + r'(20[0-9]{6}_[0-9]{6}_uefn_locomotion_[^/]+)/checkpoint_([0-9]+)(_final)?[.]zip$')

def main():
    OUT.mkdir(exist_ok=True)
    c = d.cloud.s3(); bucket = d.cloud.rp.VOLUME_ID
    active = json.loads((d.OUT / 'active_run.json').read_text())
    latest = json.loads(c.get_object(Bucket=bucket, Key=PREFIX + active['run'] + '/latest_verified.json')['Body'].read())
    assert PATTERN.fullmatch(latest['key']) and latest['key'].split('/')[-2] == active['run']
    path = d.OUT / 'preserved-latest' / active['run'] / Path(latest['key']).name
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.zip.partial')
    c.download_file(bucket, latest['key'], str(temporary))
    assert temporary.stat().st_size == latest['bytes']
    assert hashlib.sha256(temporary.read_bytes()).hexdigest() == latest['sha256']
    with zipfile.ZipFile(temporary) as z:
        assert z.testzip() is None
        state = torch.load(io.BytesIO(z.read('resume_state.pt')), map_location='cpu', weights_only=False)
    temporary.replace(path)
    receipt = dict(latest, local=str(path), iteration=state['completed_iteration'], samples=state['samples'])
    (OUT / 'preserved.json').write_text(json.dumps(receipt, indent=2))
    print('PRESERVED ' + json.dumps(receipt), flush=True)

    protected = set(json.loads((d.OUT / 'checkpoint-cleanup-plan.json').read_text())['keep'])
    protected.update(PREFIX + p.parent.name + '/' + p.name for p in (d.OUT / 'preserved-latest').glob('*/*.zip'))
    groups = {}
    for page in c.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix=PREFIX):
        for item in page.get('Contents', []):
            m = PATTERN.fullmatch(item['Key'])
            if m:
                groups.setdefault(m[1], []).append(dict(key=item['Key'], bytes=item['Size'], step=int(m[2])))
    delete = []; verified = []
    for run, items in groups.items():
        items.sort(key=lambda x: (x['step'], x['key']))
        try:
            v = json.loads(c.get_object(Bucket=bucket, Key=PREFIX + run + '/latest_verified.json')['Body'].read())
        except c.exceptions.NoSuchKey:
            continue
        m = PATTERN.fullmatch(v['key'])
        if not m or m[1] != run:
            continue
        verified.append(v['key']); protected.add(v['key'])
        protected.add(items[0]['key']); protected.update(x['key'] for x in items[-3:])
        protected.update(x['key'] for x in items if x['key'].endswith('_final.zip'))
        delete.extend(x for x in items if x['step'] < int(m[2]) and x['key'] not in protected)
    plan = dict(delete=delete, keep=sorted(protected), verified=verified, created_unix=time.time())
    (OUT / 'plan.json').write_text(json.dumps(plan, indent=2))
    print('PLAN ' + json.dumps(dict(count=len(delete), bytes=sum(x['bytes'] for x in delete))), flush=True)
    assert latest['key'] in protected and path.exists()
    def remove(item):
        assert PATTERN.fullmatch(item['key']) and item['key'] not in protected and not item['key'].endswith('_final.zip')
        c.delete_object(Bucket=bucket, Key=item['key'])
        return item
    with ThreadPoolExecutor(max_workers=6) as pool:
        removed = list(pool.map(remove, delete))
    remaining = set()
    for page in c.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix=PREFIX):
        remaining.update(x['Key'] for x in page.get('Contents', []))
    original = {x['key'] for items in groups.values() for x in items}
    assert not remaining.intersection(x['key'] for x in removed)
    assert (protected & original) <= remaining
    assert set(verified) <= remaining
    result = dict(deleted_count=len(removed), freed_bytes=sum(x['bytes'] for x in removed), retained_checkpoints=sum(bool(PATTERN.fullmatch(k)) for k in remaining), checkpoint=receipt, completed_unix=time.time(), saving_policy_changed=False)
    (OUT / 'complete.json').write_text(json.dumps(result, indent=2))
    print('COMPLETE ' + json.dumps(result), flush=True)

if __name__ == '__main__':
    main()
