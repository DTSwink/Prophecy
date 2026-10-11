import json,sys,math
from SummarizeHeadFps import angle
d=json.load(open(sys.argv[1]))
for name in d['rows'][0]['actors']:
 previous=None
 for r in d['rows']:
  v=r['actors'][name];detail=v.get('authored')
  if previous and previous.get('authored') and not detail:
   a=previous['authored'];print(name,'exit',r['tick'],'signed coordinates',{k:a[k] for k in ['correction','headDelta','baseDelta','parentDelta'] if k in a},'body',a['body'],'head relative base',angle(previous['target']['head'],a['base']['head']))
   for b in ['neck_01','neck_02','head']:print(b,'exit step',angle(v['target'][b],previous['target'][b]),'pre-exit target/base',angle(previous['target'][b],a['base'][b]))
  previous=v
