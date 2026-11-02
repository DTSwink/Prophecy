"""Package only the preflighted isolated dispatch changes from pinned production."""
import copy,hashlib,json,zipfile
from pathlib import Path
import yaml
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
OUT=d.OUT/'perf-lossless-20261024'

def prepare():
    plan=json.loads((d.OUT/'getup-success-prepared.json').read_text());previous=plan['source']
    assert previous['sha256']=='cfc40dc59380abd2620cc34b9830a65b991cbfa7ee27046b2c06185173fbbf1b'
    report=json.loads(r.remote("from pathlib import Path;import json;p=Path('/workspace/mimickit_trial/perf-lossless-20261024/runtime-preflight-complete.json');print(p.read_text())"))
    assert len(report['reward_checks'])==27 and len(report['nonfinite_checks'])==9
    (OUT/'runtime-preflight-complete.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (OUT/'previous-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    overlays={p.relative_to(OUT/'candidate').as_posix():p.read_bytes() for p in (OUT/'candidate').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    source=OUT/'source-stored.zip'
    with zipfile.ZipFile(previous['local']) as old,zipfile.ZipFile(source,'w') as new:
        names=set(old.namelist())
        for info in old.infolist():new.writestr(copy.copy(info),overlays.get(info.filename,old.read(info.filename)))
        for name in sorted(set(overlays)-names):
            info=zipfile.ZipInfo(name,(2026,10,24,0,0,0));info.create_system=3;info.external_attr=0o600<<16;info.compress_type=zipfile.ZIP_STORED
            new.writestr(info,overlays[name])
    with zipfile.ZipFile(previous['local']) as old,zipfile.ZipFile(source) as new:
        changed=sorted(n for n in old.namelist() if old.read(n)!=new.read(n))
        assert changed==['pipeline/absolute_walk.py','pipeline/perturbed_omni.py','pipeline/train.py','prepared/env_config.yaml'],changed
        a=yaml.safe_load(old.read('prepared/env_config.yaml'));b=yaml.safe_load(new.read('prepared/env_config.yaml'));assert b.pop('lossless_dispatch') is True and a==b
        assert new.testzip() is None
    sha=hashlib.sha256(source.read_bytes()).hexdigest();key='mimickit/pipeline_20261014/lossless-dispatch/source_'+sha[:12]+'.zip'
    plan.update(source=dict(local=str(source),key=key,sha256=sha),run_suffix='uefn_locomotion_dispatch_2048')
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    code='''import copy,hashlib,json,zipfile,boto3
from pathlib import Path
r=Path('/workspace/mimickit_trial');p=r/'perf-lossless-20261024'
assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==OLD
with zipfile.ZipFile(p/'candidate-overlay.zip') as z:overlays={n:z.read(n) for n in z.namelist()}
with zipfile.ZipFile(r/'source.zip') as old,zipfile.ZipFile(p/'source-stored.zip','w') as new:
 names=set(old.namelist())
 for info in old.infolist():new.writestr(copy.copy(info),overlays.get(info.filename,old.read(info.filename)))
 for name in sorted(set(overlays)-names):
  info=zipfile.ZipInfo(name,(2026,10,24,0,0,0));info.create_system=3;info.external_attr=0o600<<16;info.compress_type=zipfile.ZIP_STORED
  new.writestr(info,overlays[name])
data=(p/'source-stored.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);c.put_object(Bucket='aj7d2jzwuq',Key=KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()).hexdigest()==SHA
print('Candidate source digest and persistent readback verified')
'''.replace('OLD',repr(previous['sha256'])).replace('SHA',repr(sha)).replace('KEY',repr(key))
    print(r.remote(code,timeout=60),flush=True)
    active=json.loads((d.OUT/'active_run.json').read_text());d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod'],source=plan['source']))
    (OUT/'package-diff.json').write_text(json.dumps(dict(changed=changed,added=sorted(set(overlays)-names),source_sha256=sha),indent=2),encoding='utf-8')
    print(json.dumps(dict(source=plan['source'],changed=changed)),flush=True)

if __name__=='__main__':prepare()
