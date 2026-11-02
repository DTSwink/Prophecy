"""Bounded range transfer for this deployment; hashes verified by callers."""
import concurrent.futures, json, urllib.request, time, hashlib, zipfile, sys
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
def download(item,path):
 url=item.get('download_url',item.get('url'));headers=item.get('download_headers',item.get('headers'))
 def get(start,end):
  for attempt in range(3):
   try:
    with urllib.request.urlopen(urllib.request.Request(url,headers=dict(headers,Range=f'bytes={start}-{end}')),timeout=25) as r:
     assert r.status==206
     data=r.read();total=int(r.headers['Content-Range'].split('/')[-1]);assert len(data)==min(end+1,total)-start
     return start,data,total
   except Exception:
    if attempt==2:raise
    time.sleep(1)
 _,_,total=get(0,1023);chunk=2*1024*1024
 with path.open('wb') as f,concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
  f.truncate(total)
  for start,data,_ in pool.map(lambda start:get(start,min(start+chunk,total)-1),range(0,total,chunk)):
   f.seek(start);f.write(data)
 print('Range download complete',path.name,total,flush=True)
if sys.argv[1]=='artifacts':
 for label,item in json.loads((ROOT/'success-download.json').read_text()).items():
  p=ROOT/(label+'.ranged');download(item,p);assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'];p.replace(ROOT/(label+'.zip'))
 with zipfile.ZipFile(ROOT/'source.zip') as z:z.extractall(ROOT)
 (ROOT/'success-download-ready').touch()
else:
 sys.path.insert(0,str(ROOT/'pipeline'));import runtime_cache;runtime_cache.download=download;runtime_cache.restore()
