"""Preserve latest, calibrate once, resume locomotion with a walking-height cap."""
import hashlib,json,sys,zipfile,time
from pathlib import Path
import yaml
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
from walking_height import patch_source


def stage():
    files={name:Path(__file__).with_name(name).read_text() for name in ['calibrate_walking_height.py']}
    files['walking-height-reference.json']=(d.OUT/'walking-height-reference.json').read_text()
    print(r.remote("from pathlib import Path\nr=Path('/workspace/mimickit_trial')\nfor n,s in "+repr(files)+".items():(r/n).write_text(s)\nprint('Calibration staged; trainer untouched')"),flush=True)


def capture():
    p=json.loads((d.OUT/'ae30-switch.json').read_text())
    code='''from pathlib import Path
import json,hashlib,time,shutil,subprocess
r=Path('/workspace/mimickit_trial');p=r/'runs'/OLD
for _ in range(16):
 if (p/'finished.json').exists():break
 time.sleep(2)
assert (p/'finished.json').exists(),'Trainer not finished'
b=json.loads((p/'backup_status.json').read_text());assert b['key'].endswith('_final.zip')
cp=p/Path(b['key']).name;assert hashlib.sha256(cp.read_bytes()).hexdigest()==b['sha256']
shutil.copyfile(cp,r/'resume.zip');(r/'walking-height-calibration.json').unlink(missing_ok=True)
with (r/'walking-height-calibration.log').open('ab') as log:
 process=subprocess.Popen(['timeout','240',str(r/'venv/bin/python'),str(r/'calibrate_walking_height.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps(dict(**b,calibration_pid=process.pid)))
'''.replace('OLD',repr(p['old_run']))
    cp=json.loads(r.remote(code));d.save('walking-height-pending-checkpoint',cp)
    dest=d.OUT/'preserved-latest'/p['old_run']/Path(cp['key']).name;dest.parent.mkdir(parents=True,exist_ok=True)
    part=dest.with_suffix('.part');d.cloud.s3().download_file(d.cloud.rp.VOLUME_ID,cp['key'],str(part))
    assert hashlib.sha256(part.read_bytes()).hexdigest()==cp['sha256']
    with zipfile.ZipFile(part) as z:assert z.testzip() is None
    part.replace(dest);cp.update(local=str(dest),preserved_key=cp['key'])
    p['checkpoint']=cp;d.save('ae30-switch',p);d.save('walking-height-checkpoint',cp)
    print(json.dumps(cp),flush=True)


def prepare():
    report=json.loads(r.remote("from pathlib import Path;print(Path('/workspace/mimickit_trial/walking-height-calibration.json').read_text())"))
    cp=json.loads((d.OUT/'walking-height-checkpoint.json').read_text());assert report['checkpoint_sha256']==cp['sha256']
    d.save('walking-height-calibration',report)
    old=json.loads((d.OUT/'walking-height-before-plan.json').read_text());ref=json.loads((d.OUT/'walking-height-reference.json').read_text())
    with zipfile.ZipFile(old['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    entries['pipeline/perturbed_omni.py']=patch_source(entries['pipeline/perturbed_omni.py'].decode()).encode()
    entries['pipeline/walking_height.py']=Path(__file__).with_name('walking_height.py').read_bytes()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml']);cfg['perturbed_motion'].update(walking_height_weight=report['weight'],walking_height_reference=ref)
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode();entries['prepared/walking_height_calibration.json']=json.dumps(report,indent=2).encode()
    source=d.OUT/'walking-height-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries.items():z.writestr(name,data)
    data=source.read_bytes();sha=hashlib.sha256(data).hexdigest();key='mimickit/pipeline_20261014/walking-height/source_'+sha[:12]+'.zip'
    d.cloud.s3().put_object(Bucket=d.cloud.rp.VOLUME_ID,Key=key,Body=data)
    # Verify persistent readback beside the GPU, avoiding a second WAN download.
    code='''from pathlib import Path
import json,boto3,hashlib,zipfile,io
r=Path('/workspace/mimickit_trial');p=json.loads((r/'private.json').read_text());c=boto3.client('s3',**p['s3'])
data=c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read();assert hashlib.sha256(data).hexdigest()==SHA
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==CP_SHA
(r/'source.zip').write_bytes(data)
with zipfile.ZipFile(io.BytesIO(data)) as z:z.extractall(r)
p['resume_checkpoint']=CHECKPOINT;(r/'private.json').write_text(json.dumps(p));(r/'stop.request').unlink(missing_ok=True)
print('Source persistent readback verified and deployed; latest checkpoint verified')
'''.replace('CP_SHA',repr(cp['sha256'])).replace('KEY',repr(key)).replace('SHA',repr(sha)).replace('CHECKPOINT',repr(dict(key=cp['key'],sha256=cp['sha256'])))
    print(r.remote(code,timeout=60),flush=True)
    old.update(checkpoint=cp,source=dict(local=str(source),key=key,sha256=sha),run_suffix='uefn_locomotion_walk_height2_1024')
    d.save('getup-success-prepared',old);print(json.dumps(report),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='stop':r.stop()
    elif sys.argv[1]=='launch':d.launch()
    else:globals()[sys.argv[1]]()
