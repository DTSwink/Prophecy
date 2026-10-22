"""Protected latest-checkpoint restart for the locomotion speed limits."""
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
import yaml
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
from loco_extremity_speed import patch_source, check


def prepare():
    base=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    active=json.loads((d.OUT/'active_run.json').read_text())
    report=json.loads((d.OUT/'extremity-speed-reference.json').read_text())
    rows={x['id']:x for x in report['motions']}
    for name,row in rows.items():
        reference=name
        if 'Stand_Idle_Loop' in name:
            reference=name.replace('Stand_Idle_Loop','Walk_Loop_B')
        row['reference_id']=reference
        if reference!=name:
            row['own_max_m_s']=row['max_m_s']
            row['max_m_s']=rows[reference]['max_m_s']
            row['limits_m_s']=rows[reference]['limits_m_s']
    report['idle_reference']='matching equipment Walk_Loop_B'
    (d.OUT/'extremity-speed-reference.json').write_text(json.dumps(report,indent=2))
    with zipfile.ZipFile(base['source']['local']) as z: entries={n:z.read(n) for n in z.namelist()}
    before=entries['pipeline/perturbed_omni.py'].decode()
    after=patch_source(before)
    tests=check(after)
    entries['pipeline/perturbed_omni.py']=after.encode()
    entries['prepared/extremity_speed_reference.json']=json.dumps(report,indent=2).encode()
    cfg=yaml.safe_load(entries['prepared/env_config.yaml'])
    cfg['perturbed_motion']['extremity_speed_reference']='/workspace/mimickit_trial/prepared/extremity_speed_reference.json'
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    source=d.OUT/'locomotion-extremity-speed-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries.items():z.writestr(name,data)
    data=source.read_bytes();sha=hashlib.sha256(data).hexdigest()
    key='mimickit/pipeline_20261014/locomotion-extremity-speed/source_'+sha[:12]+'.zip'
    c=d.cloud.s3();c.put_object(Bucket=d.cloud.rp.VOLUME_ID,Key=key,Body=data)
    d.verified_readback(c,d.cloud.rp.VOLUME_ID,key,sha)
    shared=Path(__file__).with_name('perturbed_omni.py')
    if 'def _extremity_speed_failure' not in shared.read_text():
        shared.write_text(patch_source(shared.read_text()))
    d.save('extremity-speed-before-plan',base)
    d.save('extremity-speed-old-launch',json.loads((d.OUT/'launch.json').read_text()))
    plan=dict(old_run=active['run'],pod=active['pod'],source=dict(local=str(source),key=key,sha256=sha))
    d.save('ae30-switch',plan);d.save('extremity-speed-switch',plan)
    d.save('extremity-speed-source-verification',dict(tests=tests,changed=['pipeline/perturbed_omni.py','prepared/env_config.yaml','prepared/extremity_speed_reference.json'],source=plan['source']))
    print(json.dumps(dict(prepared=plan,tests=tests)),flush=True)


def capture():
    r.capture()
    p=json.loads((d.OUT/'ae30-switch.json').read_text())
    d.save('extremity-speed-preserved-checkpoint',p['checkpoint'])


def launch():
    p=json.loads((d.OUT/'ae30-switch.json').read_text());source=p['source'];cp=p['checkpoint']
    code='''import json,hashlib,zipfile,io
from pathlib import Path
import boto3
r=Path('/workspace/mimickit_trial');p=json.loads((r/'private.json').read_text())
c=boto3.client('s3',**p['s3']);data=c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()
assert hashlib.sha256(data).hexdigest()==SOURCE_SHA
assert hashlib.sha256((r/'resume.zip').read_bytes()).hexdigest()==CP_SHA
(r/'source.zip').write_bytes(data)
with zipfile.ZipFile(io.BytesIO(data)) as z:z.extractall(r)
p['resume_checkpoint']=CHECKPOINT
(r/'private.json').write_text(json.dumps(p))
(r/'stop.request').unlink(missing_ok=True)
print('Source and final checkpoint verified')
'''.replace('KEY',repr(source['key'])).replace('SOURCE_SHA',repr(source['sha256'])).replace('CP_SHA',repr(cp['sha256'])).replace('CHECKPOINT',repr(dict(key=cp['key'],sha256=cp['sha256'])))
    print(r.remote(code),flush=True)
    base=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    base.update(source=source,checkpoint=cp,worlds=1024,run_suffix='uefn_locomotion_extremity_speed_1024')
    d.save('getup-success-prepared',base)
    d.launch()


if __name__=='__main__':
    if sys.argv[1]=='stop':r.stop()
    else:globals()[sys.argv[1]]()
