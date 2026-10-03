exec(open('Saved/Diagnostics/AnalyzeHead187.py').read().split("for t in range(1,max(r)+1)")[0])
rr={x['tick']:x for x in json.loads((p/'Head187-repeat-capture.json').read_text())['rows']}
print('repeat max position error',max(np.linalg.norm(np.array(x['targets'][n]['target']['p'])-rr[t]['targets'][n]['target']['p']) for t,x in r.items() for n in x['targets']))
for t in range(177,193):
 print(t,'alpha',r[t]['alpha'],'head per-tick',np.round(np.array(b(t,'head')['p'])-b(t-1,'head')['p'],4),'pelvis',np.round(np.array(b(t,'pelvis')['p'])-b(t-1,'pelvis')['p'],4),'pin',r[t]['pin'])
data=[json.loads(l) for l in (p/'Head187-baseline-nn.jsonl').read_text().splitlines()]
print('trace keys',list(data[0]));print('first samples',[(x.get('frame'),x.get('time'),x.get('actor'),x.get('kind')) for x in data[:6]])
