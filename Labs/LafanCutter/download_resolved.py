"""Fetch the author's BVH data; safe extraction, no executable content."""
from pathlib import Path
import shutil
import urllib.request
import zipfile
import json
from motion import atomic_json

ROOT = Path.home() / 'Downloads' / 'LAFAN-Re-solved'
ROOT.mkdir(exist_ok=True)
archive = ROOT / 'bvh.zip'
url = 'https://theorangeduck.com/media/uploads/Geno/lafan1-resolved/bvh.zip'
if not archive.exists():
    part = ROOT / 'bvh.zip.part'
    with urllib.request.urlopen(url, timeout=60) as response, part.open('wb') as f:
        size = int(response.headers['Content-Length'])
        if shutil.disk_usage(ROOT).free < size * 5:
            raise RuntimeError('Insufficient disk space for archive and extraction')
        done = 0
        while chunk := response.read(4*1024*1024):
            f.write(chunk); done += len(chunk)
            atomic_json(ROOT / 'download-status.json', dict(bytes=done, total=size, stage='download'))
    if done != size:
        raise RuntimeError('Incomplete download')
    part.replace(archive)
with zipfile.ZipFile(archive) as z:
    entries = [i for i in z.infolist() if i.filename.lower().endswith('.bvh')]
    size = sum(i.file_size for i in entries)
    if shutil.disk_usage(ROOT).free < size + 512*1024*1024:
        raise RuntimeError('Insufficient disk space to extract BVH files')
    for n, info in enumerate(entries):
        target = (ROOT / info.filename).resolve()
        if not target.is_relative_to(ROOT.resolve()):
            raise ValueError('Unsafe archive path')
        target.parent.mkdir(parents=True, exist_ok=True)
        with z.open(info) as source, target.open('wb') as dest:
            shutil.copyfileobj(source, dest)
        atomic_json(ROOT / 'download-status.json', dict(stage='extract', done=n+1, total=len(entries)))
atomic_json(ROOT / 'download-status.json', dict(stage='complete', clips=len(entries), extracted_bytes=size, url=url))
print(json.dumps(dict(clips=len(entries), extracted_bytes=size, root=str(ROOT))))
