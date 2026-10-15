"""Scoped Runpod control for the isolated MimicKit trial; never touches other pods."""
import argparse
import hashlib
import json
import os
import re
import shlex
import sys
import subprocess
import tempfile
import time
from pathlib import Path
import requests
import boto3

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get('MIMICKIT_STATE_DIR',ROOT/'Saved/MimicKit')).resolve()
sys.path.insert(0, r'C:/Users/singerie/Documents/Cursor/stepper/training/runpod')
import slash2_runpod as rp

def graphql(query):
    r = requests.post('https://api.runpod.io/graphql', headers={'Authorization':'Bearer '+rp.load_api_key()},
                      json={'query':query}, timeout=30)
    r.raise_for_status()
    body = r.json()
    if body.get('errors'):
        raise RuntimeError(body['errors'])
    return body['data']

def credentials():
    user = graphql('query { myself { id } }')['myself']['id']
    secret = re.search(r'rps_[A-Za-z0-9_-]+', rp.KEYS_FILE.read_text()).group(0)
    return dict(aws_access_key_id=user, aws_secret_access_key=secret,
                endpoint_url='https://s3api-eu-ro-1.runpod.io', region_name='EU-RO-1')

def s3():
    return boto3.client('s3', **credentials())

def state():
    return json.loads((OUT/'pod.json').read_text())

def save(value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'pod.json').write_text(json.dumps(value, indent=2))

def allocate(gpu, ceiling, cloud_type='COMMUNITY', seconds=7200, name='mimickit-walk-20261014'):
    assert not (OUT/'pod.json').exists(), 'Reconcile existing allocation before retry'
    existing = [p for p in rp.request_json('GET','/pods') if p.get('name') == name]
    assert not existing, 'Named pod already exists; reconcile instead of creating duplicate'
    public = rp.PRIVATE_KEY.with_suffix('.pub').read_text().strip()
    payload = dict(name=name,cloudType=cloud_type,computeType='GPU',
                   gpuTypeIds=[gpu],gpuTypePriority='custom',gpuCount=1,
                   imageName='runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04',
                   containerDiskInGb=40,volumeInGb=20,volumeMountPath='/workspace',
                   minVCPUPerGPU=4,minRAMPerGPU=16,ports=['22/tcp'],supportPublicIp=True,
                   interruptible=False,env={'PUBLIC_KEY':public,'SSH_PUBLIC_KEY':public},
                   dockerEntrypoint=[],dockerStartCmd=[])
    p = rp.request_json('POST','/pods',payload)
    info = dict(pod_id=p['id'],name=name,gpu=gpu,cost_per_hour=p.get('costPerHr'),
                created_unix=time.time(),max_initial_runtime_seconds=seconds,cloud_type=cloud_type)
    save(info)  # Record identity before any further action.
    if not 0 < float(p.get('costPerHr',999)) <= ceiling:
        rp.request_json('POST',f"/pods/{p['id']}/stop")
        raise RuntimeError('Unexpected price; owned pod stopped')
    print(json.dumps(info))

def connect():
    info=state()
    info['connection']=rp.wait_for_connection(info['pod_id'],timeout_seconds=45)
    save(info)
    return info['connection']

def ssh(command, timeout=45):
    result=subprocess.run(rp.ssh_base(state()['connection'])+['bash','-lc',shlex.quote(command)],
                          timeout=timeout,capture_output=True,encoding='utf-8',errors='replace')
    if result.returncode:
        raise RuntimeError(f'Remote exit {result.returncode}: '+result.stdout[-2000:]+result.stderr[-2000:])
    return result.stdout

def prepare_runtime_cache():
    client=s3()
    cfg=credentials()
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    from botocore.credentials import Credentials
    def authorize(item):
        url=cfg['endpoint_url']+'/'+rp.VOLUME_ID+'/'+item['key']
        request=AWSRequest(method='GET',url=url,headers={'User-Agent':'MimicKit-runtime-cache/1.0',
            'X-Amz-Content-SHA256':hashlib.sha256(b'').hexdigest()})
        SigV4Auth(Credentials(cfg['aws_access_key_id'],cfg['aws_secret_access_key']),
                  's3',cfg['region_name']).add_auth(request)
        item.update(download_url=url,download_headers=dict(request.headers))
    manifest=json.loads(client.get_object(Bucket=rp.VOLUME_ID,Key='mimickit/runtime/latest_verified.json')['Body'].read())
    authorize(manifest)
    kernels=json.loads(client.get_object(Bucket=rp.VOLUME_ID,Key='mimickit/runtime/kernels_verified.json')['Body'].read())
    authorize(kernels)
    manifest['kernels']=kernels
    # Runpod requires header authentication (query-signed URLs were rejected).
    # Never print the short-lived headers or leave them in source/control logs.
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'runtime-cache.json';path.write_text(json.dumps(manifest))
        rp.scp(state()['connection'],path,'/workspace/mimickit_trial/runtime-cache.json',timeout=45)
    ssh('chmod 600 /workspace/mimickit_trial/runtime-cache.json')
    print(json.dumps(dict(key=manifest['key'],bytes=manifest['bytes'],ready=True)))

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['allocate','connect','ssh','upload','backup','cache-hint'])
    p.add_argument('--gpu');p.add_argument('--ceiling',type=float,default=.85)
    p.add_argument('--cloud',choices=['COMMUNITY','SECURE'],default='COMMUNITY')
    p.add_argument('--seconds',type=int,default=7200)
    p.add_argument('--file');p.add_argument('--remote');p.add_argument('--shell');a=p.parse_args()
    if a.command=='allocate': allocate(a.gpu,a.ceiling,a.cloud,a.seconds)
    elif a.command=='connect': print(json.dumps(connect()))
    elif a.command=='cache-hint': prepare_runtime_cache()
    elif a.command=='ssh': print(ssh(a.shell))
    elif a.command=='upload': rp.scp(state()['connection'],Path(a.file),a.remote,timeout=60)
    elif a.command=='backup':
        path=Path(a.file);key='mimickit/pipeline_20261014/'+path.name
        c=s3();data=path.read_bytes();sha=hashlib.sha256(data).hexdigest()
        c.put_object(Bucket=rp.VOLUME_ID,Key=key,Body=data,Metadata={'sha256':sha})
        restored=c.get_object(Bucket=rp.VOLUME_ID,Key=key)['Body'].read()
        assert hashlib.sha256(restored).hexdigest()==sha
        print(json.dumps(dict(key=key,bytes=len(data),sha256=sha,verified=True)))
