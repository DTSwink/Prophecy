import json,statistics as st,pathlib,sys
p=pathlib.Path('Saved/Diagnostics/AttackPerformance')
tags=sys.argv[1:] or ['baseline_a','baseline_b','optimized_a','ownership_mixed_reference','ownership_mixed_optimized','ownership_isolated_reference','ownership_isolated_optimized']
out={}
for tag in tags:
    file=p/(tag+'.json')
    if not file.exists():continue
    data=json.loads(file.read_text());rows=data['rows'][180:];modes={}
    for mode in ['locomotion','full','half']:
        group=[r for r in rows if (r['full']>0 if mode=='full' else r['half']>0 if mode=='half' else r['full']==r['half']==0)]
        if not group:continue
        keys=sorted({k for r in group for k in r['networks']})
        nets={k:dict(ms=st.mean(r['networks'].get(k,{}).get('ms',0) for r in group),calls=sum(r['networks'].get(k,{}).get('calls',0) for r in group)) for k in keys}
        stages={k:st.mean(r['ms'][k] for r in group) for k in group[0]['ms']}
        times=sorted(r['world_ms'] for r in group)
        modes[mode]=dict(frames=len(group),world_mean=st.mean(times),world_median=st.median(times),world_p95=times[int(.95*(len(times)-1))],stages=stages,networks=nets)
        print(tag,mode,len(group),'world',round(st.mean(times),3),'ms','networks',[(k,round(v['ms'],3),v['calls']) for k,v in nets.items()])
    out[tag]=modes
(p/'analysis.json').write_text(json.dumps(out,indent=2))
