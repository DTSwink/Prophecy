"""Restore the previous calibrated early MSE, retaining the current pinned run."""
import copy, hashlib, inspect, json, sys, zipfile
from pathlib import Path
import yaml
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
import resume_pushed_idle_penalty as handoff

OUT=d.OUT/'restore-prior-mse-20261025'
WEIGHT=0.010628431805636024

def prepare():
    OUT.mkdir(exist_ok=True)
    plan=json.loads((d.OUT/'getup-success-prepared.json').read_text())
    active=json.loads((d.OUT/'active_run.json').read_text())
    previous=plan['source']
    assert previous['sha256']=='140ce560e43629e4ef6bd109425c303b2685d240c37871ed083841a10433e83b'
    assert active['run']=='20261025_184729_uefn_locomotion_head_com2_2048'
    assert hashlib.sha256(Path(previous['local']).read_bytes()).hexdigest()==previous['sha256']
    (OUT/'previous-plan.json').write_text(json.dumps(plan,indent=2))
    with zipfile.ZipFile(previous['local']) as old:
        cfg=yaml.safe_load(old.read('prepared/env_config.yaml'))
        assert cfg['perturbed_motion']['ae_mse_weight']==0
        cfg['perturbed_motion']['ae_mse_weight']=WEIGHT
        final=old.read('pipeline/final_locomotion.py').decode()
        token='ae_mse_weight=0.,'
        assert final.count(token)==1
        final=final.replace(token,"ae_mse_weight=float(self.env._perturb_cfg.get('ae_mse_weight', 0.)),")
        compile(final,'final_locomotion.py','exec')
        # Exercise the actual reward method over the established P/P+/P-minus schedule.
        import resume_idle_prior_20261025 as checks
        code=inspect.getsource(checks.check)
        code=code.replace('ae_mse_weight=0.',f'ae_mse_weight={WEIGHT!r}')
        code=code.replace('[2*regular]*4',f'[2*(regular+{WEIGHT!r}*(1-regular))]*4')
        code=code.replace('[2*minus]*4',f'[2*(minus+{WEIGHT!r}*(1-minus))]*4')
        scope=dict(vars(checks));exec(code,scope)
        results=scope['check'](old.read('pipeline/perturbed_omni.py').decode())
        overlays={'prepared/env_config.yaml':yaml.safe_dump(cfg,sort_keys=False).encode(),
                  'pipeline/final_locomotion.py':final.encode()}
        source=OUT/'source-stored.zip'
        with zipfile.ZipFile(source,'w') as new:
            for info in old.infolist():new.writestr(copy.copy(info),overlays.get(info.filename,old.read(info.filename)))
        with zipfile.ZipFile(source) as new:
            changed=[n for n in old.namelist() if old.read(n)!=new.read(n)]
            assert set(changed)==set(overlays) and new.testzip() is None
        with zipfile.ZipFile(OUT/'overlay.zip','w') as z:
            for name,data in overlays.items():z.writestr(name,data)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    key='mimickit/pipeline_20261014/restore-prior-mse/source_'+sha[:12]+'.zip'
    plan.update(source=dict(local=str(source),key=key,sha256=sha),run_suffix='uefn_locomotion_prior_mse_restored_2048')
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2))
    (OUT/'checks.json').write_text(json.dumps(dict(weight=WEIGHT,checks=results,changed=changed),indent=2))
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'overlay.zip','/workspace/mimickit_trial/restore-prior-mse-overlay.zip',timeout=40)
    code='''from pathlib import Path
import copy,hashlib,json,zipfile,boto3
r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==OLD
with zipfile.ZipFile(r/'restore-prior-mse-overlay.zip') as z:overlay={n:z.read(n) for n in z.namelist()}
with zipfile.ZipFile(r/'source.zip') as old,zipfile.ZipFile(r/'restore-prior-mse-source.zip','w') as new:
 for info in old.infolist():new.writestr(copy.copy(info),overlay.get(info.filename,old.read(info.filename)))
data=(r/'restore-prior-mse-source.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);c.put_object(Bucket='aj7d2jzwuq',Key=KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()).hexdigest()==SHA
print('Candidate source uploaded and persistent readback verified; trainer untouched')
'''.replace('OLD',repr(previous['sha256'])).replace('SHA',repr(sha)).replace('KEY',repr(key))
    print(r.remote(code,timeout=60),flush=True)
    d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod'],source=plan['source']))
    print(json.dumps(dict(weight=WEIGHT,checks=len(results),changed=changed,source_sha=sha)),flush=True)

def verify():
    plan=json.loads((OUT/'prepared.json').read_text())
    active=json.loads((d.OUT/'active_run.json').read_text());name=active['run']
    assert name.endswith(plan['run_suffix'])
    code='''from pathlib import Path
import json,time,hashlib,yaml,numpy as np
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
s=json.loads((p/'status.json').read_text());b=json.loads((p/'backup_status.json').read_text())
assert s['state']=='training' and time.time()-s['updated_unix']<180
assert s['iteration']>=INITIAL+10
assert not (p/'finished.json').exists() and not (p/'backup_errors.json').exists()
assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==SHA
cfg=yaml.safe_load((r/'prepared/env_config.yaml').read_text())['perturbed_motion']
assert cfg['ae_mse_weight']==WEIGHT and cfg['pushed_idle_prior_handoff']
assert cfg['ae_ticks']==30 and cfg['blend_ticks']==30 and not cfg['com2_reward_require_both']
z=np.load(p/'replay.npz');rows=json.loads(str(z['metadata']))['replay_rows']
prior=[x for x in rows if x.get('perturbed_row') or x.get('final_phase_cohort')=='idle perturbed-']
assert prior and all(x.get('ae_mse_weight')==WEIGHT for x in prior)
assert all('head_reversal' in x['loss_term_names'] and x.get('frame_com2_reward_multiplier') for x in rows)
dispatch=json.loads((p/'lossless_dispatch.json').read_text());assert dispatch['worlds']==2048 and dispatch['reference_done_graphs']
print(json.dumps(dict(run=NAME,status={k:s.get(k) for k in ['state','iteration','samples','recent_iteration_mean_seconds','training_transitions_per_second']},backup=b,prior_rows=len(prior),weight=cfg['ae_mse_weight'])))
'''.replace('NAME',repr(name)).replace('INITIAL',str(plan['checkpoint']['finished']['iteration'])).replace('SHA',repr(plan['source']['sha256'])).replace('WEIGHT',repr(WEIGHT))
    result=json.loads(r.remote(code,timeout=30));(OUT/'live-verification.json').write_text(json.dumps(result,indent=2))
    print(r.remote("from pathlib import Path;Path('/workspace/mimickit_trial/loco_ae30_handoff_complete').touch();print('Verified handoff complete')",timeout=20))
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    handoff.OUT=OUT
    if sys.argv[1] in ('stop','capture','launch'):getattr(handoff,sys.argv[1])()
    else:globals()[sys.argv[1]]()
