"""Multiply only the pinned COM2 coefficient, then guarded latest resume."""
import hashlib,json,sys,zipfile
from pathlib import Path
from datetime import datetime
import yaml
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
import resume_pushed_idle_penalty as handoff
OUT=d.OUT/'com2-x10'

def prepare():
    OUT.mkdir(exist_ok=True)
    plan=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    (OUT/'previous-plan.json').write_text(json.dumps(plan,indent=2));previous=plan['source']
    with zipfile.ZipFile(previous['local']) as old:
        before=yaml.safe_load(old.read('prepared/env_config.yaml'))
        cfg=yaml.safe_load(old.read('prepared/env_config.yaml'))
        weight=float(cfg['perturbed_motion']['com2_loss_weight'])
        cfg['perturbed_motion']['com2_loss_weight']=weight*10
        check=yaml.safe_load(yaml.safe_dump(cfg));check['perturbed_motion']['com2_loss_weight']=weight
        assert check==before
        data=yaml.safe_dump(cfg,sort_keys=False).encode()
        (OUT/'env_config.yaml').write_bytes(data)
        source=OUT/'source-stored.zip'
        with zipfile.ZipFile(source,'w') as new:
            for info in old.infolist():new.writestr(info,data if info.filename=='prepared/env_config.yaml' else old.read(info.filename))
        with zipfile.ZipFile(source) as new,zipfile.ZipFile(previous['local']) as original:
            assert [n for n in original.namelist() if original.read(n)!=new.read(n)]==['prepared/env_config.yaml']
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    plan.update(source=dict(local=str(source),sha256=sha,key='mimickit/pipeline_20261014/com2-x10/source_'+sha[:12]+'.zip'),run_suffix='uefn_locomotion_com2x10_2048')
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2))
    (OUT/'change.json').write_text(json.dumps(dict(old_weight=weight,new_weight=weight*10,only_change='perturbed_motion.com2_loss_weight'),indent=2))
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'env_config.yaml','/workspace/mimickit_trial/com2x10-env.yaml',timeout=45)
    code='''from pathlib import Path
import hashlib,json,zipfile,boto3
r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==OLD
with zipfile.ZipFile(r/'source.zip') as old,zipfile.ZipFile(r/'com2x10-source.zip','w') as new:
 for info in old.infolist():new.writestr(info,(r/'com2x10-env.yaml').read_bytes() if info.filename=='prepared/env_config.yaml' else old.read(info.filename))
data=(r/'com2x10-source.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);c.put_object(Bucket='aj7d2jzwuq',Key=KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()).hexdigest()==SHA
print('Config-only source verified in persistent storage')
'''.replace('OLD',repr(previous['sha256'])).replace('SHA',repr(sha)).replace('KEY',repr(plan['source']['key']))
    print(r.remote(code,timeout=60),flush=True)
    active=json.loads((d.OUT/'active_run.json').read_text());d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod'],source=plan['source']))
    print(json.dumps(dict(old_weight=weight,new_weight=weight*10)),flush=True)

def verify():
    name=json.loads((d.OUT/'active_run.json').read_text())['run'];assert 'com2x10_2048' in name
    initial=json.loads((OUT/'prepared.json').read_text())['checkpoint']['finished']['iteration']
    weight=json.loads((OUT/'change.json').read_text())['new_weight']
    code='''from pathlib import Path
import json,time,numpy as np,yaml
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
end=time.time()+35
while time.time()<end:
 if (p/'failure.json').exists():raise RuntimeError((p/'failure.json').read_text())
 if (p/'status.json').exists() and (p/'backup_status.json').exists():
  if json.loads((p/'status.json').read_text()).get('iteration',0)>INITIAL:break
 time.sleep(3)
s=json.loads((p/'status.json').read_text());b=json.loads((p/'backup_status.json').read_text())
assert s['state']=='training' and s['iteration']>INITIAL and time.time()-s['updated_unix']<180
assert not (p/'finished.json').exists() and not (p/'backup_errors.json').exists()
assert yaml.safe_load((p/'env_config.yaml').read_text())['perturbed_motion']['com2_loss_weight']==WEIGHT
z=np.load(p/'replay.npz');m=json.loads(str(z['metadata']))
assert all(x['com2_loss']['weight']==WEIGHT for x in m['replay_rows'])
events=EventAccumulator(str(p));events.Reload();values=events.Scalars('loss/com2_velocity');assert values
(r/'loco_ae30_handoff_complete').touch()
print(json.dumps(dict(run=NAME,status={k:s.get(k) for k in ['state','iteration','samples','worlds','training_transitions_per_second']},backup=b,com2_weight=WEIGHT,tb_com2=values[-1].value)))
'''.replace('NAME',repr(name)).replace('INITIAL',str(initial)).replace('WEIGHT',repr(weight))
    result=json.loads(r.remote(code,timeout=45));(OUT/'live-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

def journal():
    live=json.loads((OUT/'live-verification.json').read_text());plan=json.loads((OUT/'prepared.json').read_text());change=json.loads((OUT/'change.json').read_text());cp=plan['checkpoint']
    # The launch name is stamped in the configured Warsaw desktop timezone.
    now=datetime.strptime(live['run'][:15],'%Y%m%d_%H%M%S').strftime('%B %d %H:%M')
    note=f'''## {now} Warsaw - COM2 loss x10 RUNNING

User requested multiplying the existing COM2 loss by10 and resume from latest.
Only config coefficient changed: {change['old_weight']:.12g} -> {change['new_weight']:.12g}.
Same constant per-motion COM2 targets, forward/sideways leeway, all-row/all-tick
scope, termination, sampling, optimizer and physics. No recalibration.
Run {live['run']} on existing L4 w754z82j94t55a,
2048 worlds at <=$0.59/hour until stopped. Latest source checkpoint
{Path(cp['local']).name}, {cp['finished']['samples']:,} samples,
downloaded locally to {cp['local']}
and SHA256/ZIP plus persistent-readback verified. SHA {cp['sha256']}.
Advancing iteration{live['status']['iteration']}, {live['status']['samples']:,} samples;
first new backup verified, handoff guard released. loss/com2_velocity recorded
with new weight in actual replay and TB. Source diff is env_config.yaml only.
Helper Labs/MimicKitTraining/resume_com2_x10.py;
receipts Saved/MimicKitLocomotion/com2-x10. Current prepared plan updated.

'''
    for path,marker in [(d.ROOT/'ProjectJournal.md',b'## Resume here'),(d.ROOT/'Docs/MimicKitTraining.md',b'# MimicKit humanoid trial')]:
        data=path.read_bytes();at=data.index(b'\n',data.index(marker))+1;path.write_bytes(data[:at]+b'\n'+note.encode()+data[at:])

if __name__=='__main__':
    handoff.OUT=OUT
    if sys.argv[1] in ['stop','capture','launch']:getattr(handoff,sys.argv[1])()
    else:globals()[sys.argv[1]]()
