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
names={'status.json','evaluation.json','backup_status.json','finished.json','failure.json','numerical_failure.json','solver_warnings.json','backup_errors.json','replay.npz','resume.json','adaptive_rows.json'}
for line in sys.stdin:
    request=json.loads(line)
    reply={}
    if root.exists():
        for p in root.iterdir():
            if not (p.name in names or p.name.startswith('events.out.tfevents.')):continue
            stat=p.stat();version=[stat.st_mtime_ns,stat.st_size]
            old=request.get(p.name,{})
            summary=None
            if p.name in ('status.json','evaluation.json'):
                summary=json.loads(p.read_text())
                evaluation=summary.get('evaluation',summary)
                replay=evaluation.get('replay')
                if isinstance(replay,dict):
                    # Frame arrays and per-row targets already travel once in replay.npz.
                    evaluation['replay']={k:replay[k] for k in ('iteration','samples','generated_unix','duration_seconds','terminal_flag','world','mode') if k in replay}
                    evaluation['replay']['row_count']=len(replay.get('replay_rows',[])) or 1
                summary=json.dumps(summary,separators=(',',':')).encode()
            delivery_size=len(summary) if summary is not None else stat.st_size
            if old.get('version')==version and old.get('size')==delivery_size:continue
            offset=old.get('size',0) if p.name.startswith('events.') or old.get('version')==version else 0
            if offset>delivery_size:offset=0
            if summary is not None:data=summary[offset:offset+2*1024*1024]
            else:
                with p.open('rb') as file:
                    file.seek(offset);data=file.read(min(delivery_size-offset,2*1024*1024))
            reply[p.name]=dict(version=version,offset=offset,complete=offset+len(data)==delivery_size,
                              data=base64.b64encode(data).decode())
    payload=gzip.compress(json.dumps(reply,separators=(',',':')).encode(),compresslevel=3)
    print(base64.b64encode(payload).decode(),flush=True)
