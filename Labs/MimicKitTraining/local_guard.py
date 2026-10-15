"""Local fallback billing deadline, started immediately after allocating this pod."""
import json
import time
import cloud
from runtime_deadline import RuntimeDeadline

s=cloud.state()
deadline=RuntimeDeadline(cloud.OUT/'runtime_control.json',s['pod_id'],s['created_unix']+s['max_initial_runtime_seconds'])
while time.time()<deadline.read():
    time.sleep(min(5,max(0,deadline.read()-time.time())))
for attempt in range(6):
    try:
        while time.time()<deadline.read():
            time.sleep(min(5,max(0,deadline.read()-time.time())))
        cloud.rp.request_json('POST','/pods/'+s['pod_id']+'/stop')
        (cloud.OUT/'local_guard_stopped.json').write_text(json.dumps({'pod':s['pod_id'],'time':time.time()}))
        break
    except Exception:
        time.sleep(15)
