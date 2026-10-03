import pathlib,json,collections,sys
p=pathlib.Path(sys.argv[1])
rows=[json.loads(l) for l in (p/'metrics.jsonl').read_text().splitlines()]
g=collections.defaultdict(list)
for r in rows:
 if r['frame']<60:continue
 for source,pose in r['poses'].items():
  z=min(x[2] for x in pose['points'][2:])
  g[(r['agent'],r['side'],source)].append((z,r))
for key,vals in g.items():
 z,r=min(vals,key=lambda x:x[0]);print(key,'min ankle/toe',round(z,3),'frame',r['frame'],'mode',r['mode'],'attack',r['attack'],'below0',sum(x[0]<0 for x in vals))
scene=json.loads(pathlib.Path('Saved/Diagnostics/FootFloor/scene-live.json').read_text())
for r in scene['rows']: print('SCENE',r['actor'],r.get('transform'),r.get('mode'))
f=p/'pipeline.jsonl'
if f.exists():
 data=[json.loads(l) for l in f.read_text().splitlines()]; print('TRACE_KEYS',data[-1].keys() if data else [])
 for r in data[-3:]:print({k:v for k,v in r.items() if k in ['actor','agent','attack','tempering','right_foot_tempering','roots','left_walk_weight','right_walk_weight']})
