"""Retry only the owned L4 after a rejected resume configuration check."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
import deploy_locomotion_branch as d

OUT = d.OUT / 'perf-lossless-20261024'
MARKER = OUT / 'retry-verified'


def start():
    plan = json.loads((OUT / 'prepared.json').read_text())
    assert Path(plan['source']['local']).name == 'source-resume-fix.zip'
    assert hashlib.sha256(Path(plan['source']['local']).read_bytes()).hexdigest() == plan['source']['sha256']
    pod = d.cloud.state()['pod_id']
    assert pod == 'w754z82j94t55a'
    state = d.cloud.rp.request_json('GET', '/pods/' + pod)
    assert state['desiredStatus'] == 'EXITED' and 0 < float(state['costPerHr']) <= .59
    MARKER.unlink(missing_ok=True)
    deadline = time.time() + 600
    code = f'''import sys,time
from pathlib import Path
sys.path.insert(0,{str(d.ROOT / 'Labs/MimicKitTraining')!r})
import deploy_locomotion_branch as d
from billing_stop import stop_and_confirm
while time.time() < {deadline!r} and not Path({str(MARKER)!r}).exists():time.sleep(2)
if not Path({str(MARKER)!r}).exists():stop_and_confirm({pod!r},d.cloud.rp.load_api_key(),Path({str(OUT / 'retry-timeout.json')!r}),'Dispatch retry not verified within ten minutes')
'''
    with (OUT / 'retry-guard.log').open('ab') as log:
        guard = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=log, creationflags=0x08000000)
    (OUT / 'retry-guard.json').write_text(json.dumps(dict(pid=guard.pid, pod=pod, deadline=deadline)))
    try:
        d.cloud.rp.request_json('POST', '/pods/' + pod + '/start')
    except Exception:
        MARKER.touch()
        raise
    print('Existing L4 restart accepted; ten-minute setup guard active', flush=True)
    d.cloud.connect()
    print('SSH connection refreshed', flush=True)


if __name__ == '__main__':
    start()
