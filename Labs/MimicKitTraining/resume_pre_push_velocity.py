"""Restore regular perturbed velocity failure checks before the tick80 push."""
import ast,hashlib,json,pickle,sys,zipfile
from pathlib import Path
from types import SimpleNamespace
import torch
import deploy_locomotion_branch as d
import restart_locomotion_ae as r
import resume_pushed_idle_penalty as handoff

OUT=d.OUT/'pre-push-velocity'

def prepare():
    OUT.mkdir(exist_ok=True)
    plan=json.loads((d.OUT/'final-phase-prepared.json').read_text())
    (OUT/'previous-plan.json').write_text(json.dumps(plan,indent=2))
    previous=plan['source']
    key='pipeline/final_locomotion.py'
    with zipfile.ZipFile(previous['local']) as z:
        original=z.read(key)
        old=b'(self.pushed & (ticks>=130))'
        new=b'(self.pushed & ((ticks<80) | (ticks>=130)))'
        old_meta=b"velocity_gate='ticks130-150 only'"
        new_meta=b"velocity_gate='ticks9-79 and130-150; paused80-129 for push'"
        assert original.count(old)==1 and original.count(old_meta)==1
        updated=original.replace(old,new).replace(old_meta,new_meta)
        compile(updated,key,'exec')
        source=OUT/'source-stored.zip'
        with zipfile.ZipFile(source,'w') as out:
            for info in z.infolist():out.writestr(info,updated if info.filename==key else z.read(info.filename))
    local=Path(__file__).with_name('final_locomotion.py');data=local.read_bytes()
    assert data.count(old)==1 and data.count(old_meta)==1
    local.write_bytes(data.replace(old,new).replace(old_meta,new_meta))

    # Evaluate the exact production return expression with the caller's initial grace.
    def gate_expression(code):
        method=next(n for n in ast.walk(ast.parse(code)) if isinstance(n,ast.FunctionDef) and n.name=='velocity_gate')
        return compile(ast.Expression(next(n.value for n in method.body if isinstance(n,ast.Return))),'gate','eval')
    ticks=torch.tensor([0,8,9,79,80,129,130,149])
    s=SimpleNamespace(pushed=torch.ones(8,dtype=torch.bool),plus=torch.zeros(8,dtype=torch.bool),
                      first_foot=torch.full((8,),2),cfg={'plus_foot_grace':50})
    actual=eval(gate_expression(updated),dict(self=s,ticks=ticks)) & (ticks>8)
    expected=torch.tensor([False,False,True,True,False,False,True,True])
    torch.testing.assert_close(actual,expected)
    ticks=torch.arange(151);s.pushed=torch.zeros(151,dtype=torch.bool);s.plus=torch.ones(151,dtype=torch.bool);s.first_foot=torch.full((151,),2)
    torch.testing.assert_close(eval(gate_expression(updated),dict(self=s,ticks=ticks)),eval(gate_expression(original),dict(self=s,ticks=ticks)))
    with zipfile.ZipFile(source) as z,zipfile.ZipFile(OUT/'delta.zip','w',zipfile.ZIP_DEFLATED) as delta:
        delta.writestr('infos.pkl',pickle.dumps(z.infolist(),protocol=4));delta.writestr(key,z.read(key))
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    plan.update(source=dict(local=str(source),key='mimickit/pipeline_20261014/pre-push-velocity/source_'+sha[:12]+'.zip',sha256=sha),
                run_suffix='uefn_locomotion_pre_push_velocity_1024')
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2))
    (OUT/'verification.json').write_text(json.dumps(dict(boundary_ticks=[0,8,9,79,80,129,130,149],enabled=actual.tolist(),plus_unchanged=True,only_changed=key,source_sha256=sha),indent=2))
    d.cloud.rp.scp(d.cloud.state()['connection'],OUT/'delta.zip','/workspace/mimickit_trial/pre-push-delta.zip',timeout=45)
    code="""from pathlib import Path
import json,hashlib,zipfile,pickle,boto3
r=Path('/workspace/mimickit_trial');assert hashlib.sha256((r/'source.zip').read_bytes()).hexdigest()==OLD_SHA
with zipfile.ZipFile(r/'source.zip') as old,zipfile.ZipFile(r/'pre-push-delta.zip') as delta,zipfile.ZipFile(r/'pre-push-source.zip','w') as new:
 for info in pickle.loads(delta.read('infos.pkl')):new.writestr(info,delta.read(info.filename) if info.filename in delta.namelist() else old.read(info.filename))
data=(r/'pre-push-source.zip').read_bytes();assert hashlib.sha256(data).hexdigest()==SHA
c=boto3.client('s3',**json.loads((r/'private.json').read_text())['s3']);c.put_object(Bucket='aj7d2jzwuq',Key=KEY,Body=data)
assert hashlib.sha256(c.get_object(Bucket='aj7d2jzwuq',Key=KEY)['Body'].read()).hexdigest()==SHA
print('Boundary tests passed; identical source verified in persistent storage')
""".replace('OLD_SHA',repr(previous['sha256'])).replace('SHA',repr(sha)).replace('KEY',repr(plan['source']['key']))
    print(r.remote(code,timeout=60),flush=True)
    active=json.loads((d.OUT/'active_run.json').read_text())
    d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod'],source=plan['source']))

def verify():
    name=json.loads((d.OUT/'active_run.json').read_text())['run'];assert 'pre_push_velocity' in name
    initial=json.loads((OUT/'prepared.json').read_text())['checkpoint']['finished']['iteration']
    code="""from pathlib import Path
import json,time
r=Path('/workspace/mimickit_trial');p=r/'runs'/NAME;end=time.time()+35
while True:
 s=json.loads((p/'status.json').read_text()) if (p/'status.json').exists() else {}
 if s.get('iteration',0)>INITIAL or time.time()>end:break
 time.sleep(3)
assert s.get('state')=='training' and s['iteration']>INITIAL and time.time()-s['updated_unix']<180, ('not ready',s.get('iteration'))
b=json.loads((p/'backup_status.json').read_text());assert b['key'].split('/')[-2]==NAME
assert not (p/'finished.json').exists() and not (p/'backup_errors.json').exists()
rows=json.loads((p/'evaluation.json').read_text())['replay']['replay_rows']
regular=[{k:v for k,v in row.items() if k in ['final_phase_cohort','terminal_flag','velocity_gate','duration_seconds']} for row in rows if row.get('final_phase_cohort')=='perturbed']
assert regular and all('ticks9-79' in row['velocity_gate'] for row in regular)
(r/'loco_ae30_handoff_complete').touch()
print(json.dumps(dict(run=NAME,status={k:s.get(k) for k in ['state','iteration','samples','training_transitions_per_second']},backup=b,regular_perturbed=regular)))
""".replace('NAME',repr(name)).replace('INITIAL',str(initial))
    result=json.loads(r.remote(code,timeout=45));(OUT/'live-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
    handoff.OUT=OUT
    action=sys.argv[1]
    if action in ['stop','capture','launch']:getattr(handoff,action)()
    else:globals()[action]()
