import json,statistics as st,pathlib,sys
root=pathlib.Path('Saved/Diagnostics');report={}
for tag in sys.argv[1:]:
 d=json.loads((root/'AttackPerformance'/f'{tag}.json').read_text(encoding='utf-8-sig'));groups={'idle':[],'attack':[],'return':[]};since=1000
 for i,r in enumerate(d['rows']):
  active=r['full']+r['half']>0
  since=0 if active else since+1
  if i<90:continue
  key='attack' if active else 'return' if since<=20 else 'idle'
  groups[key].append(r)
 result={}
 for k,g in groups.items():
  if not g:continue
  ms={n:st.mean(r['ms'][n] for r in g) for n in g[0]['ms']};keys=sorted({n for r in g for n in r['networks']})
  nets={n:dict(ms=st.mean(r['networks'].get(n,{}).get('ms',0) for r in g),calls=sum(r['networks'].get(n,{}).get('calls',0) for r in g)) for n in keys}
  result[k]=dict(frames=len(g),world_mean=st.mean(r['world_ms'] for r in g),world_median=st.median(r['world_ms'] for r in g),stages=ms,networks=nets,full=sum(r['full'] for r in g),half=sum(r['half'] for r in g))
  print(tag,k,len(g),'world',round(result[k]['world_mean'],3),'median',round(result[k]['world_median'],3),'networks',nets)
  print('stages',sorted(((n,round(v,3)) for n,v in ms.items() if v>.05),key=lambda x:-x[1]))
 report[tag]=result
(root/'AttackPerformance20261002/analysis.json').write_text(json.dumps(report,indent=2),encoding='utf8')
