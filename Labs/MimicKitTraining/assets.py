"""Fetch only the stock walking clip using ZIP byte ranges (no full asset archive)."""
import io
import json
import hashlib
import zipfile
from pathlib import Path
import requests

URL = 'https://1sfu-my.sharepoint.com/:u:/g/personal/xbpeng_sfu_ca/EclKq9pwdOBAl-17SogfMW0Bved4sodZBQ_5eZCiz9O--w?download=1'

class RemoteZip(io.RawIOBase):
    def __init__(self):
        self.session = requests.Session()
        r = self.session.get(URL, headers={'Range': 'bytes=0-0'}, timeout=30)
        r.raise_for_status()
        assert r.status_code == 206
        self.size = int(r.headers['Content-Range'].split('/')[-1])
        self.position = 0
        self.downloaded = len(r.content)

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        return self.position

    def tell(self):
        return self.position

    def seekable(self):
        return True

    def read(self, size=-1):
        size = self.size - self.position if size < 0 else min(size, self.size - self.position)
        if not size:
            return b''
        r = self.session.get(URL, headers={'Range': f'bytes={self.position}-{self.position+size-1}'}, timeout=30)
        r.raise_for_status()
        assert r.status_code == 206 and len(r.content) == size
        self.position += size
        self.downloaded += size
        return r.content

def fetch(repository, motion='humanoid_walk'):
    assert motion in ('humanoid_walk', 'humanoid_spinkick')
    remote = RemoteZip()
    with zipfile.ZipFile(remote) as archive:
        body = archive.read(f'MimicKit_Data/motions/humanoid/{motion}.pkl')
    path = Path(repository)/f'data/motions/humanoid/{motion}.pkl'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    receipt = dict(source=URL, selected_file=str(path), bytes=len(body), downloaded_bytes=remote.downloaded,
                   archive_bytes=remote.size, sha256=hashlib.sha256(body).hexdigest())
    print(json.dumps(receipt))
    return receipt

if __name__ == '__main__':
    import sys
    fetch(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else 'humanoid_walk')
