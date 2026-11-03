"""User-authorized intermediates only; preserve latest, finals and local pins."""
import json,re,time,zipfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import deploy_slow_policy as d
from deploy_saved_sitting import remote
D=d.OUT/'action-jiggle-20261103/checkpoint-cleanup';D.mkdir(exist_ok=True)
a=json.loads((d.OUT/'active_run.json').read_text());v=json.loads((D.parent/'verified.json').read_text())
assert a['state']=='running_verified' and v['passed'] and v['run']==a['run']
main=json.loads((d.OUT/'crawl-relaunch-20261102/main-protected.json').read_text())
assert d.sha(main['downloaded_copy'])==main['sha256']
import boto3
from botocore.config import Config
c=boto3.client('s3',config=Config(connect_timeout=10,read_timeout=10,retries={'max_attempts':0},max_pool_connections=12),**d.cloud.credentials());bucket=d.cloud.rp.VOLUME_ID;prefix='mimickit/pipeline_20261014/runs/'
pattern=re.compile(r'^(20\d{6}_\d{6}_uefn_slowloco_[a-z0-9_]+)/checkpoint_(\d+)(_final)?\.zip$')
latest=json.loads(c.get_object(Bucket=bucket,Key=prefix+a['run']+'/latest_verified.json')['Body'].read())
assert pattern.fullmatch(latest['key'][len(prefix):])[1]==a['run']
local=d.OUT/'preserved-latest'/a['run']/Path(latest['key']).name;local.parent.mkdir(parents=True,exist_ok=True)
part=local.with_suffix('.zip.part');c.download_file(bucket,latest['key'],str(part))
assert d.sha(part)==latest['sha256']
with zipfile.ZipFile(part) as z:assert z.testzip() is None and {'model.pt','resume_state.pt'}<=set(z.namelist())
part.replace(local);d.write(D/'preserved.json',dict(**latest,local=str(local)))
keep={main['backup']['key'],latest['key']}
keep.update(prefix+p.parent.name+'/'+p.name for p in (d.OUT/'preserved-latest').glob('*/*.zip'))
def list_slow_objects():
 dirs=[]
 for page in c.get_paginator('list_objects_v2').paginate(Bucket=bucket,Prefix=prefix,Delimiter='/'):
  dirs.extend(x['Prefix'] for x in page.get('CommonPrefixes',[]) if re.fullmatch(r'20\d{6}_\d{6}_uefn_slowloco_[a-z0-9_]+/',x['Prefix'][len(prefix):]))
 print('Scanning checkpoint prefixes in',len(dirs),'slow-loco runs',flush=True)
 def listing(folder):
  return [o for page in c.get_paginator('list_objects_v2').paginate(Bucket=bucket,Prefix=folder+'checkpoint_') for o in page.get('Contents',[])]
 with ThreadPoolExecutor(max_workers=8) as pool:return [o for objects in pool.map(listing,dirs) for o in objects]
groups={}
for obj in list_slow_objects():
 m=pattern.fullmatch(obj['Key'][len(prefix):])
 if m:groups.setdefault(m[1],[]).append(dict(key=obj['Key'],bytes=obj['Size'],step=int(m[2]),final=bool(m[3])))
print('Inventoried',len(groups),'slow-loco runs',flush=True)
removed=[];verified=[]
def read_latest(run):
 try:return run,json.loads(c.get_object(Bucket=bucket,Key=prefix+run+'/latest_verified.json')['Body'].read())
 except Exception as error:
  print('Keeping entire run; latest receipt unavailable:',run,type(error).__name__,flush=True)
  return run,None
with ThreadPoolExecutor(max_workers=8) as pool:receipts=dict(pool.map(read_latest,groups))
print('Protected latest records checked',flush=True)
for run,items in groups.items():
 r=receipts[run]
 if r is None:continue
 m=pattern.fullmatch(r['key'][len(prefix):]);assert m and m[1]==run
 keep.add(r['key']);verified.append(r['key']);keep.update(o['key'] for o in items if o['final'])
 if run==a['run']:keep.update(o['key'] for o in sorted(items,key=lambda x:x['step'])[-3:])
 removed.extend(o for o in items if o['step']<int(m[2]) and o['key'] not in keep and not o['final'])
d.write(D/'plan.json',dict(delete=removed,protected=sorted(keep)))
with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(lambda o:c.delete_object(Bucket=bucket,Key=o['key']),removed))
remaining={o['Key'] for o in list_slow_objects()}
assert not remaining.intersection(o['key'] for o in removed)
assert set(verified)|{main['backup']['key'],latest['key']}<=remaining
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
pod=json.loads(remote(code));report=dict(persistent_files=len(removed),persistent_bytes=sum(o['bytes'] for o in removed),pod=pod,latest=latest,local=str(local),main_checkpoint=20414,skipped_runs=[k for k,v in receipts.items() if v is None],completed_unix=time.time())
d.write(D/'complete.json',report);print(json.dumps(report))
