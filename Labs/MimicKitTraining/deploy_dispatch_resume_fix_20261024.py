"""Rebuild a verified source from retained bytes plus the small resume-gate fix."""
import json
from pathlib import Path
import deploy_locomotion_branch as d
import restart_locomotion_ae as r

out = d.OUT / 'perf-lossless-20261024'
plan = json.loads((out / 'prepared.json').read_text())
d.cloud.rp.scp(d.cloud.state()['connection'], out / 'candidate/pipeline/train.py',
               '/workspace/mimickit_trial/perf-lossless-20261024/train-resume-fix.py', timeout=40)
code = '''import copy,hashlib,json,zipfile,boto3
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'perf-lossless-20261024'
assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()=='813432a21c3e8864b082bfb3e065b2c2874552d47b4b4549039c57f4563ad5a4'
with zipfile.ZipFile(r/'source.zip') as old,zipfile.ZipFile(p/'source-resume-fix.zip','w') as new:
 for info in old.infolist():new.writestr(copy.copy(info),(p/'train-resume-fix.py').read_bytes() if info.filename=='pipeline/train.py' else old.read(info.filename))
data=(p/'source-resume-fix.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SOURCE_SHA
private=json.loads((r/'private.json').read_text());c=boto3.client('s3',**private['s3'])
c.put_object(Bucket='aj7d2jzwuq',Key=SOURCE_KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=SOURCE_KEY)['Body'].read()).hexdigest()==SOURCE_SHA
(r/'source.zip').write_bytes(data)
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==CHECKPOINT_SHA
(r/'stop.request').unlink(missing_ok=True)
print(json.dumps(dict(source_sha256=SOURCE_SHA,checkpoint_sha256=CHECKPOINT_SHA,persistent_readback=True)))
'''.replace('SOURCE_SHA', repr(plan['source']['sha256'])).replace('SOURCE_KEY', repr(plan['source']['key'])).replace('CHECKPOINT_SHA', repr(plan['checkpoint']['sha256']))
receipt = json.loads(r.remote(code, timeout=60))
(out / 'resume-fix-source-verification.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt), flush=True)
d.launch()
