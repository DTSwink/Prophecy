import json,time,urllib.request
from pathlib import Path
root=Path(__file__).parent
for distance in [.6,.823797974]:
 data=json.dumps(dict(attack='hookL',orbit=0,facing=0,distance=distance)).encode()
 req=urllib.request.Request('http://127.0.0.1:8941/api/generate',data=data,headers={'Content-Type':'application/json'})
 job=json.load(urllib.request.urlopen(req))['job']
 for _ in range(100):
  row=json.load(urllib.request.urlopen('http://127.0.0.1:8941/api/jobs/'+job))
  if row['status'] in ['done','error','superseded']:break
  time.sleep(.5)
 assert row['status']=='done',row
 name='updated_viewer_'+('60' if distance==.6 else '82')+'.json'
 (root/name).write_text(json.dumps(row['result']))
 print(name,row['result']['scenario'],flush=True)
