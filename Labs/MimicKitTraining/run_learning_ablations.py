"""Run a bounded sequential diagnostic queue; never mutate the live run."""
import json,subprocess,sys,time
from pathlib import Path
out=Path(sys.argv[1]); plan=json.loads((out/'plan.json').read_text())
queue=sys.argv[2:] or list(plan['variants'])
r=Path('/workspace/mimickit_trial'); state={'started':time.time(),'completed':[],'queue':queue}
def save():
    tmp=out/'queue_status.tmp';tmp.write_text(json.dumps(state,indent=2));tmp.replace(out/'queue_status.json')
for key in queue:
    if (out/'cancel.request').exists():state['cancelled']=True;break
    state['active']=key;save()
    with (out/(key+'.log')).open('wb') as log:
        p=subprocess.Popen(['nice','-n','10',str(r/'venv/bin/python'),'-u',str(r/'pipeline/audit_learning_ablations.py'),str(out),key],stdout=log,stderr=log,stdin=subprocess.DEVNULL)
        try:code=p.wait(timeout=min(1800,plan.get('variant_timeout_seconds',700)))
        except subprocess.TimeoutExpired:p.kill();p.wait();code=124
    if code:
        state['failed']={'variant':key,'exit_code':code};save();sys.exit(1)
    value=json.loads((out/('result_'+key+'.json')).read_text())
    if not value.get('complete'):raise RuntimeError('Incomplete result '+key)
    state['completed'].append(key);save()
state['active']=None;state['finished']=time.time();save()
