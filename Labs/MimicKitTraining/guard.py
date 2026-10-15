"""Stop only the owned paid pod at the recorded deadline, even if setup fails."""
import json
import time
import urllib.request
from pathlib import Path
from runtime_deadline import RuntimeDeadline

root=Path('/workspace/mimickit_trial')
control=json.loads((root/'private.json').read_text())
deadline=RuntimeDeadline(root/'runtime_control.json',control['pod_id'],control['deadline_unix']+120)
request=urllib.request.Request('https://rest.runpod.io/v1/pods/'+control['pod_id']+'/stop',
    headers={'Authorization':'Bearer '+control['runpod_api_key']},method='POST')
for attempt in range(6):
    try:
        while time.time() < deadline.read():
            time.sleep(min(5,max(0,deadline.read()-time.time())))
        with urllib.request.urlopen(request,timeout=30) as response:
            assert response.status < 300
        (root/'billing_stopped.json').write_text(json.dumps({'time':time.time(),'reason':'bounded trial deadline'}))
        break
    except Exception as error:
        print(type(error).__name__,flush=True)
        time.sleep(15)
