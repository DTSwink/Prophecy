"""Use AWS's managed multipart downloader rather than single-request urllib."""
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

ROOT = Path('/workspace/mimickit_trial')


def main():
    import boto3
    from botocore.config import Config
    from boto3.s3.transfer import TransferConfig
    private = json.loads((ROOT/'private.json').read_text())
    plan = json.loads((ROOT/'success-plan.json').read_text())
    client = boto3.client('s3', **private['s3'], config=Config(
        connect_timeout=15, read_timeout=90,
        retries={'mode': 'standard', 'total_max_attempts': 3}))
    transfer = TransferConfig(max_concurrency=4, multipart_chunksize=16*1024*1024,
                              num_download_attempts=3)
    bucket = 'aj7d2jzwuq'

    def download(item, path):
        client.download_file(bucket, item['key'], str(path), Config=transfer)
        with path.open('rb') as source:
            sha = hashlib.file_digest(source, 'sha256').hexdigest()
        if sha != item['sha256']:
            raise RuntimeError('Downloaded file checksum mismatch')
        print(path.name+' verified', flush=True)

    download(plan['source'], ROOT/'source.zip')
    download(dict(key=plan['checkpoint']['preserved_key'],
                  sha256=plan['checkpoint']['sha256']), ROOT/'resume.zip')
    with zipfile.ZipFile(ROOT/'source.zip') as archive:
        archive.extractall(ROOT)
    cache = json.loads(client.get_object(
        Bucket=bucket, Key='mimickit/runtime/latest_verified.json')['Body'].read())
    cache['kernels'] = json.loads(client.get_object(
        Bucket=bucket, Key='mimickit/runtime/kernels_verified.json')['Body'].read())
    (ROOT/'runtime-cache.json').write_text(json.dumps(cache))
    sys.path.insert(0, str(ROOT/'pipeline'))
    import runtime_cache
    runtime_cache.download = download
    runtime_cache.restore()
    (ROOT/'success-download-ready').touch()


if __name__ == '__main__':
    main()
