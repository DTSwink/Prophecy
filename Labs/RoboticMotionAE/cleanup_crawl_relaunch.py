"""Scoped slow-loco intermediate cleanup; all finals/latest/local pins retained."""
import sys,json,re,time
sys.path.insert(0,'Labs/RoboticMotionAE')
import deploy_crawl_only_experiment as x
D=x.OUT/'crawl-relaunch-20261102';c=x.d.cloud.s3();bucket=x.d.cloud.rp.VOLUME_ID;prefix='mimickit/pipeline_20261014/runs/'
m=json.loads((D/'main-protected.json').read_text());e=json.loads((D/'experiment-resume.json').read_text())
assert x.d.sha(m['downloaded_copy'])==m['sha256'] and x.d.sha(e['local'])==e['sha256']
pattern=re.compile(r'^(20\d{6}_\d{6}_uefn_slowloco_[a-z0-9_]+)/checkpoint_(\d+)(_final)?\.zip$')
keep={m['backup']['key'],e['key']}
keep.update(prefix+p.parent.name+'/'+p.name for p in (x.OUT/'preserved-latest').glob('*/*.zip'))
groups={}
for page in c.get_paginator('list_objects_v2').paginate(Bucket=bucket,Prefix=prefix):
 for obj in page.get('Contents',[]):
  match=pattern.fullmatch(obj['Key'][len(prefix):])
  if match:groups.setdefault(match[1],[]).append(dict(key=obj['Key'],bytes=obj['Size'],step=int(match[2]),final=bool(match[3])))
removed=[]
for run,items in groups.items():
 try:r=json.loads(c.get_object(Bucket=bucket,Key=prefix+run+'/latest_verified.json')['Body'].read())
 except c.exceptions.NoSuchKey:continue
 match=pattern.fullmatch(r['key'][len(prefix):]);assert match and match[1]==run
 keep.add(r['key']);keep.update(o['key'] for o in items if o['final'])
 removed.extend(o for o in items if o['step']<=int(match[2]) and o['key'] not in keep)
x.d.write(D/'cleanup-plan.json',dict(delete=removed,protected=sorted(keep)))
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=8) as pool:
 list(pool.map(lambda o:c.delete_object(Bucket=bucket,Key=o['key']),removed))
remaining=set()
for page in c.get_paginator('list_objects_v2').paginate(Bucket=bucket,Prefix=prefix):remaining.update(o['Key'] for o in page.get('Contents',[]))
assert not remaining.intersection(o['key'] for o in removed)
assert m['backup']['key'] in remaining and e['key'] in remaining
names=[o['key'][len(prefix):] for o in removed]
code="""from pathlib import Path
import re,json,shutil
root=Path('/workspace/mimickit_trial/runs').resolve();deleted=[]
for name in NAMES:
 assert re.fullmatch(r'20\d{6}_\d{6}_uefn_slowloco_[a-z0-9_]+/checkpoint_\d+\.zip',name)
 p=root/name;assert not p.is_symlink() and p.resolve().is_relative_to(root)
 if p.exists():
  n=p.stat().st_size;p.unlink();deleted.append(n)
print(json.dumps(dict(files=len(deleted),bytes=sum(deleted),free_bytes=shutil.disk_usage(root).free)))
""".replace('NAMES',repr(names))
pod=json.loads(x.remote(code));report=dict(persistent_files=len(removed),persistent_bytes=sum(o['bytes'] for o in removed),pod=pod,main_checkpoint=20414,experiment_checkpoint=20425,completed_unix=time.time())
x.d.write(D/'cleanup-complete.json',report);print(json.dumps(report))
