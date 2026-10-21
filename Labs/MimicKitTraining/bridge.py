"""Low-data local bridge: incremental TensorBoard events, small replay, no checkpoints."""
import json
import os
import base64
import gzip
from pathlib import Path
import subprocess
import time
import argparse
import re
from datetime import datetime
import cloud
from runtime_deadline import RuntimeDeadline
from replay import convert

STEPPER=Path(r'C:/Users/singerie/Documents/Cursor/stepper')

def atomic_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,separators=(',',':')));temp.replace(path)

def publish_rollout(debug,payload):
    """Keep every received capture before replacing the live pointer."""
    archive=debug/f"rollout_step_{int(payload['step']):08d}.json"
    if not archive.exists():atomic_json(archive,payload)
    captured=datetime.fromisoformat(payload['computed_at']).timestamp()
    os.utime(archive,(captured,captured))
    atomic_json(debug/'last_batch_rollout.json',payload)

def receive_file(local,item,validate=None):
    """Validate chunk continuity and the completed replay before publishing it."""
    offset=item['offset'];data=base64.b64decode(item['data'])
    target=local if local.name.startswith('events.') else local.with_suffix('.part')
    if offset and (not target.exists() or target.stat().st_size!=offset):
        raise ValueError(f'{local.name}: missing or mismatched partial download at {offset}')
    with target.open('ab' if offset else 'wb') as stream:
        stream.write(data)
    payload=None
    if item.get('complete',True):
        if validate is not None:payload=validate(target)
        if target!=local:target.replace(local)
    return payload

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--name',default='humanoid_walk_01')
    parser.add_argument('--poll-seconds',type=float,default=30);args=parser.parse_args()
    assert args.poll_seconds>=5
    assert re.fullmatch(r'[A-Za-z0-9_]+',args.name)
    run='mimickit_'+args.name
    local_root=STEPPER/'training/runs'/run
    s=cloud.state();conn=s['connection']
    geom=json.loads((cloud.OUT/'geometry.json').read_text())
    local_root.mkdir(parents=True,exist_ok=True)
    debug=local_root/'debug';debug.mkdir(exist_ok=True)
    downloaded=0;seen={};client=None;started=time.time()
    deadline=RuntimeDeadline(cloud.OUT/'runtime_control.json',s['pod_id'],s['created_unix']+s['max_initial_runtime_seconds'],reserve=-180)
    while time.time()<deadline.read():
        try:
            if client is None:
                client=subprocess.Popen(cloud.rp.ssh_base(conn)+['python','-u','/workspace/mimickit_trial/pipeline/telemetry.py',args.name],
                                        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
            client.stdin.write(json.dumps(seen)+'\n');client.stdin.flush()
            line=client.stdout.readline()
            if not line:raise ConnectionError('Telemetry SSH connection closed')
            downloaded+=len(line)
            files=json.loads(gzip.decompress(base64.b64decode(line)))
            errors=[]
            for name,item in files.items():
                local=local_root/name
                try:
                    payload=receive_file(local,item,
                        (lambda path:convert(path,geom,run)) if name=='replay.npz' else None)
                    if payload is not None:publish_rollout(debug,payload)
                    seen[name]=dict(version=item['version'],size=item['offset']+len(base64.b64decode(item['data'])))
                except Exception as error:
                    # Retry the WHOLE file, not its final chunk. Keep other telemetry flowing.
                    seen.pop(name,None)
                    errors.append(f'{name}: {type(error).__name__}: {error}')
            finished=(local_root/'finished.json').exists() or (local_root/'failure.json').exists()
            warning=local_root/'solver_warnings.json'
            if warning.exists() and (debug/'last_batch_rollout.json').exists():
                detail=json.loads(warning.read_text())
                payload=json.loads((debug/'last_batch_rollout.json').read_text())
                if payload.setdefault('metadata',{}).get('solver_warning')!=detail:
                    payload['metadata']['solver_warning']=detail
                    atomic_json(debug/'last_batch_rollout.json',payload)
            alerts=[]
            for alert in ['failure.json','numerical_failure.json','backup_errors.json']:
                if (local_root/alert).exists():alerts.append(dict(source=alert,detail=json.loads((local_root/alert).read_text())))
            if alerts:
                if (debug/'last_batch_rollout.json').exists():
                    payload=json.loads((debug/'last_batch_rollout.json').read_text())
                    payload.setdefault('metadata',{})['training_health']=dict(state='ERROR',alerts=alerts)
                    atomic_json(debug/'last_batch_rollout.json',payload)
                if not (local_root/'alert_announced.json').exists():
                    print('TRAINING ALERT '+args.name+': '+json.dumps(alerts),flush=True)
                    if os.name=='nt':
                        import winsound
                        try:winsound.MessageBeep(winsound.MB_ICONHAND)
                        except (OSError,RuntimeError):pass  # Muted/unavailable audio must not block telemetry.
                    atomic_json(local_root/'alert_announced.json',alerts)
            if not finished:
                atomic_json(debug/'training.active.json',dict(pid=os.getpid(),kind='remote_mimickit'))
            else:
                (debug/'training.active.json').unlink(missing_ok=True)
            atomic_json(cloud.OUT/(args.name+'-bridge-status.json'),dict(downloaded_bytes=downloaded,elapsed_seconds=time.time()-started,
                        updated_unix=time.time(),finished=finished,checkpoint_downloads=False))
            error_path=cloud.OUT/(args.name+'-bridge-error.txt')
            if errors:error_path.write_text('\n'.join(errors))
            else:error_path.unlink(missing_ok=True)
            if finished:break
        except Exception as error:
            (cloud.OUT/(args.name+'-bridge-error.txt')).write_text(f'{type(error).__name__}: {error}')
            if client:client.terminate()
            client=None
        time.sleep(args.poll_seconds)
    if client:client.terminate()
    (debug/'training.active.json').unlink(missing_ok=True)

if __name__=='__main__':main()
