import json,pathlib,numpy as np,sys
p=pathlib.Path('Saved/Diagnostics');tag=sys.argv[1] if len(sys.argv)>1 else 'length';a=json.loads((p/'Pelvis360V2-baseline-capture.json').read_text())['rows'];b=json.loads((p/('Pelvis360V2-'+tag+'-capture.json')).read_text())['rows']
pre=max(np.linalg.norm(np.array(x['targets'][n]['target']['p'])-y['targets'][n]['target']['p']) for x,y in zip(a,b) if x['tick']<=366 for n in x['targets']);print('prefix max cm',pre)
out=[]
for rows,name in ((a,'baseline'),(b,tag)):
 result=[]
 for i,r in enumerate(rows):
  if i and 365<=r['tick']<=381:
   d=np.array(r['targets']['pelvis']['target']['p'])-rows[i-1]['targets']['pelvis']['target']['p'];result.append(dict(tick=r['tick'],delta=d.tolist(),flat=float(np.linalg.norm(d[:2]))))
 print(name,[(x['tick'],round(x['flat'],3),round(x['delta'][2],3)) for x in result[::2]]);out.append(dict(mode=name,rows=result))
(p/('Pelvis360V2-'+tag+'-comparison.json')).write_text(json.dumps(dict(prefix_cm=pre,comparisons=out),indent=2))
