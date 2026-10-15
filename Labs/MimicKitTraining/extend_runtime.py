"""Apply a user-authorized deadline to the live trainer and both billing guards."""
import argparse
import json
import math
import time
import cloud

def extend(hard_stop=None, *, until_stopped=False):
    # Finite sentinel keeps already-running deadline readers compatible: they
    # deliberately reject Infinity. Explicit metadata records the authorization.
    if until_stopped:
        hard_stop = 253402300799.0  # 9999-12-31 UTC
    assert math.isfinite(hard_stop) and hard_stop > time.time()+180
    state=cloud.state()
    control=dict(pod_id=state['pod_id'],hard_stop_unix=hard_stop,updated_unix=time.time())
    control['until_stopped'] = until_stopped
    payload=json.dumps(control)
    code="""import json,os
from pathlib import Path
r=Path('/workspace/mimickit_trial')
value=json.loads(PAYLOAD)
private=json.loads((r/'private.json').read_text())
assert private['pod_id']==value['pod_id']
p=r/'runtime_control.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value));os.replace(tmp,p)
# Compatibility for future starts, not the live clock's source of truth.
private['deadline_unix']=value['hard_stop_unix']-120
p=r/'private.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(private));os.chmod(tmp,0o600);os.replace(tmp,p)
print(json.dumps(value))
""".replace('PAYLOAD',repr(payload))
    remote=json.loads(cloud.ssh("python - <<'PY'\n"+code+'\nPY'))
    assert remote==control
    path=cloud.OUT/'runtime_control.json';tmp=path.with_suffix('.tmp');tmp.write_text(payload);tmp.replace(path)
    state['hard_stop_unix']=hard_stop
    state['until_stopped']=until_stopped
    state['max_initial_runtime_seconds']=hard_stop-state['created_unix']
    cloud.save(state)
    print(json.dumps(control))
    return control

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--seconds',type=float,default=3600)
    p.add_argument('--from-unix',type=float,help='Use actual launch time for a fresh restart; otherwise extend from now')
    p.add_argument('--until-stopped',action='store_true',help='Requires explicit authorization for ongoing GPU billing')
    a=p.parse_args()
    assert a.seconds>0
    extend((a.from_unix if a.from_unix is not None else time.time())+a.seconds, until_stopped=a.until_stopped)
