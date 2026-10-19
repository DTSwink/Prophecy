"""Stop only the owned paid pod at the recorded deadline, even if setup fails."""
import json
import time
from pathlib import Path
from runtime_deadline import RuntimeDeadline
from billing_stop import stop_and_confirm

root=Path('/workspace/mimickit_trial')
control=json.loads((root/'private.json').read_text())
deadline=RuntimeDeadline(root/'runtime_control.json',control['pod_id'],control['deadline_unix']+120)
while time.time() < deadline.read():
    time.sleep(min(5,max(0,deadline.read()-time.time())))
stop_and_confirm(control['pod_id'],control['runpod_api_key'],root/'billing_stopped.json','bounded trial deadline')
