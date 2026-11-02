"""One-time authorized persistent locomotion intermediate-checkpoint cleanup."""
import hashlib,json,sys,zipfile
from pathlib import Path
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
OUT=d.OUT/'overnight-cleanup-20261025'

def prepare():
    OUT.mkdir(exist_ok=True)
    inventory=json.loads(r.remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/loco-cleanup-inventory.json').read_text())",timeout=25))
    (OUT/'inventory.json').write_text(json.dumps(inventory,indent=2))
    cp=inventory['latest'];path=d.OUT/'preserved-latest'/cp['key'].split('/')[-2]/Path(cp['key']).name
    path.parent.mkdir(parents=True,exist_ok=True)
    c=d.cloud.s3();d.verified_readback(c,d.cloud.rp.VOLUME_ID,cp['key'],cp['sha256'])
    c.download_file(d.cloud.rp.VOLUME_ID,cp['key'],str(path))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==cp['sha256']
    with zipfile.ZipFile(path) as z:assert z.testzip() is None
    (OUT/'preserved.json').write_text(json.dumps(dict(**cp,local=str(path)),indent=2))
    protected=set(json.loads((d.OUT/'checkpoint-cleanup-plan.json').read_text())['keep'])
    for p in (d.OUT/'preserved-latest').glob('*/*.zip'):
        protected.add('mimickit/pipeline_20261014/runs/'+p.parent.name+'/'+p.name)
    (OUT/'protected.json').write_text(json.dumps(sorted(protected)))
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'protected.json','/workspace/mimickit_trial/loco-cleanup-protected.json',timeout=30)
    print(json.dumps(dict(preserved=str(path),sha256=cp['sha256'],bytes=cp['bytes'])),flush=True)

def clean():
    assert (OUT/'preserved.json').exists()
    code='''import json,re,time,hashlib
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import boto3
r=Path('/workspace/mimickit_trial');inv=json.loads((r/'loco-cleanup-inventory.json').read_text())
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);bucket='aj7d2jzwuq'
keep=set(json.loads((r/'loco-cleanup-protected.json').read_text()));groups=defaultdict(list)
pattern=re.compile(r'^mimickit/pipeline_20261014/runs/(20[0-9]{6}_[0-9]{6}_uefn_locomotion_[^/]+)/checkpoint_([0-9]+)(_final)?[.]zip$')
for x in inv['items']:
 m=pattern.fullmatch(x['key'])
 if m:groups[m[1]].append((int(m[2]),x))
delete=[];verified=[]
for name,items in groups.items():
 items.sort(key=lambda x:(x[0],x[1]['key']))
 prefix='mimickit/pipeline_20261014/runs/'+name+'/'
 try:latest=json.loads(c.get_object(Bucket=bucket,Key=prefix+'latest_verified.json')['Body'].read())
 except c.exceptions.NoSuchKey:continue
 m=pattern.fullmatch(latest['key'])
 if not m or m[1]!=name:continue
 verified.append(latest['key']);keep.add(latest['key'])
 keep.add(items[0][1]['key']);keep.update(x['key'] for _,x in items[-3:])
 keep.update(x['key'] for _,x in items if x['key'].endswith('_final.zip'))
 delete.extend(x for step,x in items if step<int(m[2]) and x['key'] not in keep)
for x in delete:
 assert pattern.fullmatch(x['key']) and not x['key'].endswith('_final.zip') and x['key'] not in keep
plan=dict(delete=delete,keep=sorted(keep),verified=verified,created_unix=time.time())
(r/'loco-cleanup-plan-20261025.json').write_text(json.dumps(plan))
def remove(x):
 c.delete_object(Bucket=bucket,Key=x['key']);return x
with ThreadPoolExecutor(max_workers=6) as pool:removed=list(pool.map(remove,delete))
remaining=set()
for page in c.get_paginator('list_objects_v2').paginate(Bucket=bucket,Prefix='mimickit/pipeline_20261014/runs/'):
 remaining.update(x['Key'] for x in page.get('Contents',[]))
assert not remaining.intersection(x['key'] for x in removed)
assert set(verified)<=remaining
original={x['key'] for x in inv['items']}
assert (keep & original)<=remaining
p=r/'runs/20261025_230729_uefn_locomotion_prior_mse_restored_2048'
s=json.loads((p/'status.json').read_text());assert s['state']=='training' and time.time()-s['updated_unix']<180
assert not (p/'finished.json').exists() and not (p/'backup_errors.json').exists()
result=dict(deleted_count=len(removed),freed_bytes=sum(x['bytes'] for x in removed),retained_checkpoints=len([k for k in remaining if pattern.fullmatch(k)]),verified_resume_points=len(verified),status={k:s.get(k) for k in ['state','iteration','samples','updated_unix']},saving_policy_changed=False)
(r/'loco-cleanup-complete-20261025.json').write_text(json.dumps(result));print(json.dumps(result))
'''
    result=json.loads(r.remote(code,timeout=150));(OUT/'complete.json').write_text(json.dumps(result,indent=2))
    plan=json.loads(r.remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/loco-cleanup-plan-20261025.json').read_text())",timeout=25))
    (OUT/'plan.json').write_text(json.dumps(plan,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':globals()[sys.argv[1]]()
