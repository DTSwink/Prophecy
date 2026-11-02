"""Preserve latest locally, then remove only verified slow-loco intermediates."""
import json,re,zipfile,time
from pathlib import Path
import deploy_slow_policy as d
from deploy_saved_sitting import remote

def main():
    out=d.OUT/'checkpoint-cleanup-20261101';out.mkdir(exist_ok=True)
    client=d.cloud.s3();bucket=d.cloud.rp.VOLUME_ID;prefix='mimickit/pipeline_20261014/runs/'
    pattern=re.compile(r'^(20\d{6}_\d{6}_uefn_slowloco_unperturbed_2048)/checkpoint_(\d+)(_final)?\.zip$')
    state=json.loads((d.OUT/'active_run.json').read_text());active=state['run']
    deployment=json.loads((d.OUT/'reference-upper-deploy-20261101/deployment-verified.json').read_text())
    assert state['state']=='running_verified' and deployment['verified'] and deployment['run']==active
    assert state['pod']==d.cloud.state()['pod_id']=='5xs589fdlcb7nr'
    latest=json.loads(client.get_object(Bucket=bucket,Key=prefix+active+'/latest_verified.json')['Body'].read())
    match=pattern.fullmatch(latest['key'][len(prefix):]);assert match and match[1]==active
    local=d.OUT/'preserved-latest'/active/Path(latest['key']).name;local.parent.mkdir(parents=True,exist_ok=True)
    part=local.with_suffix('.zip.part');client.download_file(bucket,latest['key'],str(part))
    assert part.stat().st_size==latest['bytes'] and d.sha(part)==latest['sha256']
    with zipfile.ZipFile(part) as z:assert z.testzip() is None and {'model.pt','resume_state.pt'}<=set(z.namelist())
    part.replace(local);d.write(out/'preserved.json',dict(**latest,local=str(local)))
    protected={prefix+p.parent.name+'/'+p.name for p in (d.OUT/'preserved-latest').glob('*/*.zip')}
    removed=[];keep=set(protected);groups={};verified=[]
    for page in client.get_paginator('list_objects_v2').paginate(Bucket=bucket,Prefix=prefix):
        for item in page.get('Contents',[]):
            m=pattern.fullmatch(item['Key'][len(prefix):])
            if m:groups.setdefault(m[1],[]).append(dict(key=item['Key'],bytes=item['Size'],step=int(m[2])))
    for run,items in groups.items():
        receipt=json.loads(client.get_object(Bucket=bucket,Key=prefix+run+'/latest_verified.json')['Body'].read())
        m=pattern.fullmatch(receipt['key'][len(prefix):]);assert m and m[1]==run
        keep.add(receipt['key']);verified.append(receipt['key'])
        items.sort(key=lambda x:(x['step'],x['key']))
        keep.update(x['key'] for x in items if x['key'].endswith('_final.zip'))
        if run==active:keep.update(x['key'] for x in items[-3:]);keep.add(items[0]['key'])
        removed.extend(x for x in items if x['step']<int(m[2]) and x['key'] not in keep)
    assert latest['key'] in keep and d.sha(local)==latest['sha256']
    d.write(out/'plan.json',dict(delete=removed,keep=sorted(keep),verified=verified))
    for item in removed:
        assert pattern.fullmatch(item['key'][len(prefix):]) and item['key'] not in keep
        client.delete_object(Bucket=bucket,Key=item['key'])
    remaining=set()
    for page in client.get_paginator('list_objects_v2').paginate(Bucket=bucket,Prefix=prefix):
        remaining.update(x['Key'] for x in page.get('Contents',[]))
    assert not remaining.intersection(x['key'] for x in removed)
    assert set(verified)<=remaining
    # Exact individual archives only, under the owned run directory; no recursive deletion.
    names=[x['key'][len(prefix):] for x in removed]
    result=json.loads(remote(f'''import json,re
from pathlib import Path
root=Path('/workspace/mimickit_trial/runs').resolve();removed=[]
for name in {names!r}:
 assert re.fullmatch(r'20\d{{6}}_\d{{6}}_uefn_slowloco_unperturbed_2048/checkpoint_\d+\.zip',name)
 p=root/name
 assert not p.is_symlink() and p.resolve().is_relative_to(root)
 if p.exists():
  size=p.stat().st_size;p.unlink();removed.append(dict(path=str(p),bytes=size))
print(json.dumps(dict(deleted=len(removed),bytes=sum(x['bytes'] for x in removed))))
'''))
    report=dict(persistent_deleted=len(removed),persistent_freed_bytes=sum(x['bytes'] for x in removed),pod=result,latest=latest,local=str(local),completed_unix=time.time())
    d.write(out/'complete.json',report);print(json.dumps(report),flush=True)

if __name__=='__main__':main()
