"""Sequential shared-GPU fairness; independent deadline and idle stop guards."""
import json,subprocess,sys,time,hashlib
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
sys.path.insert(0,str(ROOT/'pipeline'))
from billing_stop import stop_and_confirm
out=Path(sys.argv[1]);plan=json.loads((out/'plan.json').read_text())
queue=sys.argv[2:] or list(plan['variants'])
private=json.loads((ROOT/'private.json').read_text())
state=dict(started=time.time(),queue=queue,completed=[],active=None)
def save():
    state['updated_unix']=time.time();tmp=out/'queue_status.tmp';tmp.write_text(json.dumps(state));tmp.replace(out/'queue_status.json')
def stop(reason):stop_and_confirm(private['pod_id'],private['runpod_api_key'],out/'billing-stopped.json',reason)
try:
    for name in queue:
        if (out/'cancel.request').exists():break
        state['active']=name;save()
        with (out/(name+'.log')).open('wb') as log:
            proc=subprocess.Popen([str(ROOT/'venv/bin/python'),'-u',str(ROOT/'pipeline/loco_learning_sweep.py'),str(out),name],stdout=log,stderr=log,stdin=subprocess.DEVNULL)
            try:code=proc.wait(timeout=plan.get('variant_timeout_seconds',1800))
            except subprocess.TimeoutExpired:proc.kill();proc.wait();code=124
        if code:raise RuntimeError(f'{name} exited {code}')
        result=json.loads((out/('result_'+name+'.json')).read_text())
        if not result.get('complete'):raise RuntimeError('Incomplete '+name)
        state['completed'].append(name);save()
        # Small diagnostic results survive even if the machine becomes unavailable.
        import boto3
        from backup import verified_readback
        client=boto3.client('s3',**private['s3']);data=(out/('result_'+name+'.json')).read_bytes()
        key='mimickit/pipeline_20261014/locomotion-sweeps-20261021/'+name+'.json'
        client.put_object(Bucket='aj7d2jzwuq',Key=key,Body=data)
        verified_readback(client,'aj7d2jzwuq',key,hashlib.sha256(data).hexdigest())
    state.update(active=None,finished=time.time());save()
    # Allow analysis/next-stage launch briefly, then end idle billing.
    until=time.time()+300
    while time.time()<until:
        if (out/'next-stage-started').exists():sys.exit(0)
        time.sleep(5)
    stop('Sweep queue finished; no next stage requested within5minutes')
except Exception as exc:
    state.update(active=None,failed=str(exc),finished=time.time());save();stop('Sweep failed: '+str(exc));raise
