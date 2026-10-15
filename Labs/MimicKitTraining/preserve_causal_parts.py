"""Small immutable archive parts for S3 gateways that reject one large PUT."""
from pathlib import Path
import json,hashlib,time
from concurrent.futures import ThreadPoolExecutor
import boto3
from botocore.config import Config
root=Path('/workspace/mimickit_trial');archive=root/'causal_regression_complete.zip'
data=archive.read_bytes();digest=hashlib.sha256(data).hexdigest()
prefix='mimickit/pipeline_20261014/causal_regression/'+digest[:12]+'/parts/'
client=boto3.client('s3',**json.loads((root/'private.json').read_text())['s3'],
    config=Config(retries={'max_attempts':3,'mode':'standard'},connect_timeout=10,read_timeout=30))
bucket='aj7d2jzwuq';size=16*1024*1024
def upload(index):
    part=data[index*size:(index+1)*size];sha=hashlib.sha256(part).hexdigest()
    key=prefix+f'part_{index:04d}.bin'
    client.put_object(Bucket=bucket,Key=key,Body=part,Metadata={'sha256':sha})
    response=client.get_object(Bucket=bucket,Key=key)['Body'];h=hashlib.sha256()
    for chunk in iter(lambda:response.read(1024*1024),b''):h.update(chunk)
    response.close();assert h.hexdigest()==sha
    print('VERIFIED',index,flush=True)
    return dict(index=index,key=key,bytes=len(part),sha256=sha)
with ThreadPoolExecutor(max_workers=4) as pool:
    parts=list(pool.map(upload,range((len(data)+size-1)//size)))
manifest=dict(archive=archive.name,bytes=len(data),sha256=digest,parts=parts,
    reconstruction='Concatenate parts in ascending index; verify archive SHA256 before extracting.',verified_unix=time.time())
key=prefix+'manifest.json';body=json.dumps(manifest,indent=2).encode()
client.put_object(Bucket=bucket,Key=key,Body=body)
assert client.get_object(Bucket=bucket,Key=key)['Body'].read()==body
receipt=dict(key=key,archive_sha256=digest,archive_bytes=len(data),parts=len(parts),verified_unix=time.time())
(root/'causal_regression/parts_receipt.json').write_text(json.dumps(receipt,indent=2))
client.put_object(Bucket=bucket,Key=prefix+'latest_verified.json',Body=json.dumps(receipt).encode())
print(json.dumps(receipt),flush=True)
