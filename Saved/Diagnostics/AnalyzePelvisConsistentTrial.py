exec(open('Saved/Diagnostics/AnalyzePelvisWide.py').read().split("on=load('on')")[0])
base={x['tick']:x for x in json.loads((p/'PelvisWide-on-capture.json').read_text())['rows']}
for mode in ('paired','full'):
 file=p/f'PelvisConsistentTrial-{mode}-capture.json'
 if not file.exists():continue
 d=json.loads(file.read_text());r={x['tick']:x for x in d['rows']};print(mode,d['reason'],len(r));print(summary(r,350,386));t,v,w=series(r,368,386);print([(int(a),round(float(b[2]),2)) for a,b in zip(t,w)]);print('prefix',max(np.linalg.norm(np.array(base[t]['targets'][b]['target']['p'])-r[t]['targets'][b]['target']['p']) for t in r if t<=320 for b in r[t]['targets']))
