"""Reuse the tested environment on the same container image, without reinstalling.

The pod-to-storage archive never passes through the user's laptop. Restore uses
stdlib only; the controller supplies short-lived signed headers in a private hint.
"""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT=Path('/workspace/mimickit_trial')
IMAGE='runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04'
BUCKET='aj7d2jzwuq'

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def compatibility():
    import torch
    return dict(image=IMAGE,python=platform.python_version(),machine=platform.machine(),
                torch=torch.__version__,cuda=torch.version.cuda)

def download(item,path):
    request=urllib.request.Request(item['download_url'],headers=item['download_headers'])
    with urllib.request.urlopen(request,timeout=60) as source,path.open('wb') as target:
        shutil.copyfileobj(source,target,4*1024*1024)

def save():
    import boto3
    started=time.time()
    archive=Path('/tmp/mimickit-runtime.tar.gz')
    venv=(ROOT/'venv').resolve()
    assert venv.name=='venv'
    subprocess.run(['tar','-I','gzip -1','-cf',str(archive),'-C',str(venv.parent),
                    'venv','-C',str(ROOT),'runtime-freeze.txt'],check=True)
    digest=sha256(archive)
    key=f'mimickit/runtime/{digest[:16]}.tar.gz'
    s3=boto3.client('s3',**json.loads((ROOT/'private.json').read_text())['s3'])
    s3.upload_file(str(archive),BUCKET,key,ExtraArgs={'Metadata':{'sha256':digest}})
    body=s3.get_object(Bucket=BUCKET,Key=key)['Body'];h=hashlib.sha256()
    for block in iter(lambda:body.read(4*1024*1024),b''):h.update(block)
    body.close()
    assert h.hexdigest()==digest,'Runtime cache readback mismatch'
    manifest=dict(key=key,sha256=digest,bytes=archive.stat().st_size,
                  compatibility=compatibility(),created_unix=time.time(),
                  save_seconds=time.time()-started,
                  freeze_sha256=sha256(ROOT/'runtime-freeze.txt'))
    s3.put_object(Bucket=BUCKET,Key='mimickit/runtime/latest_verified.json',
                  Body=json.dumps(manifest).encode())
    (ROOT/'runtime-cache-status.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest),flush=True)

def restore():
    started=time.time()
    hint=ROOT/'runtime-cache.json'
    if not hint.exists():
        return False
    cache=json.loads(hint.read_text())
    assert compatibility()==cache['compatibility'],'Container/runtime mismatch; rebuild required'
    target=Path('/opt/mimickit-runtime')
    assert not (ROOT/'venv').exists() and not target.exists(),'Refusing to replace an existing environment'
    archive=Path('/tmp/mimickit-runtime-restore.tar.gz')
    download(cache,archive)
    assert sha256(archive)==cache['sha256'],'Runtime download checksum mismatch'
    target.mkdir()
    # Trusted, checksum-verified archive; venv contains the base Python symlinks.
    subprocess.run(['tar','-xzf',str(archive),'-C',str(target)],check=True)
    (ROOT/'venv').symlink_to(target/'venv',target_is_directory=True)
    (ROOT/'runtime-freeze.txt').write_bytes((target/'runtime-freeze.txt').read_bytes())
    if cache.get('kernels'):
        kernels=cache['kernels'];packed=Path('/tmp/mimickit-kernels-restore.tar.gz')
        download(kernels,packed)
        assert sha256(packed)==kernels['sha256'],'Kernel cache checksum mismatch'
        Path('/root/.cache').mkdir(exist_ok=True)
        subprocess.run(['tar','-xzf',str(packed),'-C','/root/.cache'],check=True)
    subprocess.run([str(ROOT/'venv/bin/python'),'-c','import newton,mujoco,mujoco_warp,torch; assert torch.cuda.is_available()'],check=True)
    (ROOT/'runtime-cache-restored.json').write_text(json.dumps(dict(
        key=cache['key'],seconds=time.time()-started,verified=True)))
    print('Restored verified runtime on container-local disk',flush=True)
    return True

def save_kernels():
    import boto3
    archive=Path('/tmp/mimickit-warp-cache.tar.gz')
    # CUDA PTX/source caches are portable within Warp's own hashed cache keys.
    # Rebuild CPU objects on each host instead of assuming identical CPU features.
    subprocess.run(['tar','--exclude=*.o','--exclude=*.cpp','-czf',str(archive),
                    '-C','/root/.cache','warp'],check=True)
    digest=sha256(archive);key=f'mimickit/runtime/warp_{digest[:16]}.tar.gz'
    s3=boto3.client('s3',**json.loads((ROOT/'private.json').read_text())['s3'])
    s3.upload_file(str(archive),BUCKET,key)
    body=s3.get_object(Bucket=BUCKET,Key=key)['Body'];h=hashlib.sha256()
    for block in iter(lambda:body.read(4*1024*1024),b''):h.update(block)
    body.close();assert h.hexdigest()==digest
    receipt=dict(key=key,sha256=digest,bytes=archive.stat().st_size)
    s3.put_object(Bucket=BUCKET,Key='mimickit/runtime/kernels_verified.json',Body=json.dumps(receipt).encode())
    (ROOT/'kernel-cache-status.json').write_text(json.dumps(receipt))
    print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='save':save()
    elif sys.argv[1]=='restore':sys.exit(0 if restore() else 3)
    elif sys.argv[1]=='save-kernels':save_kernels()
    else:raise ValueError('Use save or restore')
