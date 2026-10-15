"""One background uploader. Completed immutable files only; verified before manifest."""
import hashlib
import json
import queue
import threading
import time
from pathlib import Path
import boto3
from botocore.config import Config

class Backups:
    def __init__(self, root, credentials, prefix):
        self.root=Path(root)
        self.prefix=prefix.rstrip('/')+'/'
        self.s3=boto3.client('s3',**credentials,config=Config(retries={'max_attempts':3,'mode':'standard'},
                                                           connect_timeout=15,read_timeout=60))
        self.bucket='aj7d2jzwuq'
        self.jobs=queue.Queue()
        self.errors=[]
        self.worker=threading.Thread(target=self.work,daemon=True)
        self.worker.start()

    def submit(self, path):
        self.jobs.put(Path(path))

    def work(self):
        while True:
            path=self.jobs.get()
            try:
                data=path.read_bytes()
                sha=hashlib.sha256(data).hexdigest()
                key=self.prefix+path.name
                self.s3.put_object(Bucket=self.bucket,Key=key,Body=data,Metadata={'sha256':sha})
                # Stream readback hashes avoid claiming integrity from upload metadata alone.
                stream=self.s3.get_object(Bucket=self.bucket,Key=key)['Body']
                digest=hashlib.sha256()
                for chunk in iter(lambda:stream.read(1024*1024),b''):
                    digest.update(chunk)
                stream.close()
                assert digest.hexdigest()==sha,'Remote checksum mismatch'
                receipt=dict(key=key,bytes=len(data),sha256=sha,verified_unix=time.time())
                self.s3.put_object(Bucket=self.bucket,Key=self.prefix+'latest_verified.json',
                                    Body=json.dumps(receipt).encode())
                temp=self.root/'backup_status.tmp'
                temp.write_text(json.dumps(receipt));temp.replace(self.root/'backup_status.json')
            except Exception as error:
                self.errors.append(f'{path.name}: {type(error).__name__}: {error}')
                (self.root/'backup_errors.json').write_text(json.dumps(self.errors))
            finally:
                self.jobs.task_done()

    def wait(self):
        self.jobs.join()
        if self.errors:
            raise RuntimeError('Backup failed; local checkpoint retained; see backup_errors.json')
