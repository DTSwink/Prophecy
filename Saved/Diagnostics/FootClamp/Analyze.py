import json, pathlib, statistics
p=pathlib.Path(__file__).parent
summary={}
for label,name in [('before','Before.json'),('after','Capture.json')]:
    d=json.loads((p/name).read_text())
    result={'reason':d['reason'],'groups':{}}
    keys=sorted({(r['actor'],r['side']) for r in d['rows']})
    for actor,side in keys:
        rows=[r for r in d['rows'] if r['actor']==actor and r['side']==side and r['t']>=2]
        group={'count':len(rows),'modes':sorted({r['mode'] for r in rows})}
        for metric in ('future_gap','presented_gap','mesh_gap'):
            values=[r[metric] for r in rows if metric in r]
            if values:group[metric]={'mean_cm':statistics.mean(values),'max_cm':max(values)}
        result['groups'][actor+'/'+side]=group
    summary[label]=result
(p/'Comparison.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
