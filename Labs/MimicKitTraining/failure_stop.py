"""Preserve failure evidence and stop billing after the named trainer exits badly."""
import argparse
import hashlib
import io
import json
import time
import zipfile
from pathlib import Path

from billing_stop import stop_and_confirm


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('run')
    args=parser.parse_args()
    assert args.run and all(c.isalnum() or c=='_' for c in args.run)
    root=Path('/workspace/mimickit_trial')
    run=root/'runs'/args.run
    receipt=json.loads((root/(args.run+'-launch.json')).read_text())
    proc=Path('/proc')/str(receipt['pid'])/'cmdline'
    while proc.exists():
        try: command=proc.read_bytes().split(b'\0')
        except FileNotFoundError: break
        if args.run.encode() not in command: break
        time.sleep(5)
    control=json.loads((root/'private.json').read_text())
    # Checkpoints have their own verified uploader. Retain the small unique
    # diagnostic files separately, without replacing latest_verified.json.
    try:
        if not (run/'failure.json').exists() and not (run/'finished.json').exists():
            run.mkdir(parents=True,exist_ok=True)
            (run/'failure.json').write_text(json.dumps(dict(reason='Trainer exited without a completion receipt',time=time.time())))
        import boto3
        from botocore.config import Config
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
            for path in run.iterdir():
                if path.suffix in ('.json','.yaml','.npz','.txt') or path.name.startswith('events.'):
                    bundle.write(path,path.name)
            bundle.write(root/(args.run+'.log'),'process.log')
        data=archive.getvalue();digest=hashlib.sha256(data).hexdigest()
        key='mimickit/pipeline_20261014/runs/'+args.run+'/exit_evidence_'+digest[:12]+'.zip'
        client=boto3.client('s3',**control['s3'],config=Config(connect_timeout=5,read_timeout=15,retries={'total_max_attempts':2}))
        client.put_object(Bucket='aj7d2jzwuq',Key=key,Body=data)
        assert hashlib.sha256(client.get_object(Bucket='aj7d2jzwuq',Key=key)['Body'].read()).hexdigest()==digest
        (run/'failure_evidence_verified.json').write_text(json.dumps(dict(key=key,sha256=digest)))
    finally:
        # Stopping preserves the pod volume even if the evidence upload fails.
        stop_and_confirm(control['pod_id'],control['runpod_api_key'],root/'billing_stopped.json','owned trainer exited')


if __name__=='__main__': main()
