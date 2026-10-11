import json,pathlib,sys,statistics
from SummarizeHeadFps import angle
p=pathlib.Path(sys.argv[1]);d=json.loads(p.read_text())
for name in d['rows'][0]['actors']:
 print(name)
 reach=[r for r in d['rows'] if r['actors'][name]['fields'].get('phase')==1 and r['actors'][name]['fields'].get('progress',0)>.999]
 if reach:
  for k in ('pose_error','distance','angle'):
   v=[r['actors'][name]['fields'][k] for r in reach];print(k,'min/mean/max',min(v),statistics.mean(v),max(v))
 for r in d['rows']:
  if r['tick'] not in (25,50,60,70,80,90,100,150,300,500,700):continue
  v=r['actors'][name];print(r['tick'],v['gaze'],{k:v['fields'].get(k) for k in ('phase','pose_error','distance','angle','pose_tick','reach_ticks')})
 print('equipment',d['rows'][-1]['actors'][name].get('equipment',{}).keys())
