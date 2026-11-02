"""Use the existing guarded latest-checkpoint handoff for pushed-idle cost."""
import json
import sys
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
import deploy_final_locomotion as deploy

OUT = d.OUT / 'pushed-idle-penalty'

def stop():
    plan=json.loads((d.OUT/'ae30-switch.json').read_text())
    assert plan['old_run']==json.loads((d.OUT/'active_run.json').read_text())['run']
    assert plan['source']==json.loads((OUT/'prepared.json').read_text())['source']
    r.stop()

def capture():
    r.capture()
    checkpoint=json.loads((d.OUT/'ae30-switch.json').read_text())['checkpoint']
    plan=json.loads((OUT/'prepared.json').read_text());plan['checkpoint']=checkpoint
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2))
    d.save('final-phase-prepared',plan)
    d.save('getup-success-prepared',plan)

def launch():
    deploy.deploy()
    d.launch()

def verify():
    active=json.loads((d.OUT/'active_run.json').read_text());name=active['run']
    assert 'idle_failure100' in name
    code="""from pathlib import Path
import json,time,hashlib,yaml
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME
end=time.time()+35
while True:
 s=json.loads((p/'status.json').read_text())
 if s['iteration']>INITIAL or time.time()>end:break
 time.sleep(3)
b=json.loads((p/'backup_status.json').read_text())
assert s['state']=='training' and time.time()-s['updated_unix']<180, s['state']
assert s['iteration']>INITIAL, ('waiting for updates',s['iteration'])
assert not (p/'finished.json').exists()
assert yaml.safe_load((r/'prepared/env_config.yaml').read_text())['perturbed_motion']['pushed_idle_failure_penalty']==100
assert b['key'].split('/')[-2]==NAME
assert not (p/'backup_errors.json').exists()
evaluation=json.loads((p/'evaluation.json').read_text())
replay=evaluation.get('replay',{})
rows=replay.get('replay_rows',[])
pushed=[{k:v for k,v in row.items() if k in ['final_phase_cohort','terminal_flag','pushed_idle_failure_penalty','duration_seconds']} for row in rows if row.get('final_phase_cohort')=='idle perturbed-']
assert pushed and all(x['pushed_idle_failure_penalty']==100 for x in pushed)
(r/'loco_ae30_handoff_complete').touch()
print(json.dumps(dict(run=NAME,status={k:s.get(k) for k in ['state','iteration','samples','training_transitions_per_second']},backup=b,pushed_idle_replay=pushed)))
""".replace('NAME',repr(name)).replace('INITIAL',str(json.loads((OUT/'prepared.json').read_text())['checkpoint']['finished']['iteration']))
    result=json.loads(r.remote(code,timeout=45))
    (OUT/'live-verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)

if __name__=='__main__': globals()[sys.argv[1]]()
