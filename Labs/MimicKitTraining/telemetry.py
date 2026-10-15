"""Tiny request/response stream over SSH; only allowlisted telemetry leaves the pod."""
import base64
import gzip
import json
from pathlib import Path
import sys
import re

run=sys.argv[1] if len(sys.argv)>1 else 'humanoid_walk_01'
assert re.fullmatch(r'[A-Za-z0-9_]+',run)
root=Path('/workspace/mimickit_trial/runs')/run
names={'status.json','evaluation.json','backup_status.json','finished.json','failure.json','numerical_failure.json','backup_errors.json','replay.npz','resume.json'}
for line in sys.stdin:
    request=json.loads(line)
    reply={}
    if root.exists():
        for p in root.iterdir():
            if not (p.name in names or p.name.startswith('events.out.tfevents.')):continue
            stat=p.stat();version=[stat.st_mtime_ns,stat.st_size]
            old=request.get(p.name,{})
            if old.get('version')==version:continue
            offset=old.get('size',0) if p.name.startswith('events.') else 0
            if offset>stat.st_size:offset=0
            with p.open('rb') as file:
                file.seek(offset);data=file.read(min(stat.st_size-offset,2*1024*1024))
            # A growing event file is retried until all bytes have been transferred.
            if offset+len(data)<stat.st_size:version=None
            reply[p.name]=dict(version=version,offset=offset,data=base64.b64encode(data).decode())
    payload=gzip.compress(json.dumps(reply,separators=(',',':')).encode(),compresslevel=3)
    print(base64.b64encode(payload).decode(),flush=True)
