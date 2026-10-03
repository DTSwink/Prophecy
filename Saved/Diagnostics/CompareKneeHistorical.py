import json,pathlib,numpy as np,sys
p=pathlib.Path('Saved/Diagnostics');tags=sys.argv[1:] or ['KneeHistoricalBaseline','KneeHistorical20','KneeHistorical4']
base=None
for tag in tags:
 rows=json.loads((p/(tag+'-capture.json')).read_text(encoding='utf-8'))['rows'];m=json.loads((p/(tag+'-metrics.json')).read_text(encoding='utf-8'));D={r['clock']:r for r in rows}
 if base is None:base=D
 print(tag,'prefix',max(np.linalg.norm(np.array(r['targets'][b]['target']['p'])-base[r['clock']]['targets'][b]['target']['p']) for r in rows if r['clock']<145 for b in r['targets']))
 for side in ('l','r'):
  for a,b in [(0,10),(0,29),(28,35),(0,65)]:
   mm=[x for x in m if x['kind']=='target' and x['side']==side and a<=x['after']<=b and x['attack']=='None']
   print(side,(a,b),'max pole/thigh/knee',*[round(max(x[k] for x in mm),3) for k in ('poleturn','thighturn','kneestep')])
 pos=np.array([r['targets']['pelvis']['target']['p'] for r in rows]);acc=np.linalg.norm(np.diff(pos,n=2,axis=0),axis=1)
 print('pelvis 145-180 peak',float(np.max(acc[145-rows[0]['clock']:180-rows[0]['clock']])))
