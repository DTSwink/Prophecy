"""Local fallback billing deadline, started immediately after allocating this pod."""
import json
import time
import cloud
from pathlib import Path
from billing_stop import stop_and_confirm
from runtime_deadline import RuntimeDeadline

s=cloud.state()
deadline=RuntimeDeadline(cloud.OUT/'runtime_control.json',s['pod_id'],s['created_unix']+s['max_initial_runtime_seconds'])
failure_seen=None
reason='bounded trial deadline'
while time.time()<deadline.read():
    try:
        active=json.loads((cloud.OUT/'active_run.json').read_text())
        name=active['run']
        if active['pod']==s['pod_id'] and name and all(c.isalnum() or c=='_' for c in name):
            evidence=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_'+name)/'failure.json'
            if evidence.exists():
                # Give the remote exit watcher time to finish the small evidence
                # upload; stopping retains its volume if that watcher is broken.
                if failure_seen is None or failure_seen[0]!=name:failure_seen=(name,time.time())
                if time.time()-failure_seen[1]>=30:
                    reason='local fallback: trainer failure '+name
                    break
    except (OSError,ValueError,KeyError):pass
    time.sleep(min(5,max(0,deadline.read()-time.time())))
stop_and_confirm(s['pod_id'],cloud.rp.load_api_key(),cloud.OUT/'local_guard_stopped.json',reason)
