import json, pathlib, statistics
p=pathlib.Path(__file__).parent
r=json.loads((p/'emitters.json').read_text(encoding='utf-8-sig'))
print('success',r['success'],'error',r['error'])
out=[]
for asset in sorted({t['asset'] for t in r['trials']}):
    for mode in range(9):
        rows=[t for t in r['trials'] if t['asset']==asset and t.get('mode')==mode]
        if not rows: continue
        x=dict(asset=asset,mode=mode,median_ms=statistics.median(t['tick_ms']+t['query_ms'] for t in rows),query_ms=statistics.median(t['query_ms'] for t in rows),particle_ticks=[t['particle_ticks'] for t in rows],max_particles=[t['max_particles'] for t in rows],requests=[sum(s['submitted'] for s in t['sites']) for t in rows],exports=[sum(s['exports'] for s in t['sites']) for t in rows],hits=[sum(s['returned_hits'] for s in t['sites']) for t in rows],mismatches=[t['mismatches'] for t in rows])
        x['max_export_position_error_cm']=max(t.get('max_export_position_error_cm',-1) for t in rows)
        x['max_export_velocity_error']=max(t.get('max_export_velocity_error',-1) for t in rows)
        x['counts_match_stock']=all(t.get('export_count_matches_stock',False) for t in rows)
        out.append(x);print(json.dumps(x))
    for t in r['trials']:
        if t['asset']==asset and t.get('mode')==1:
            for s in t['sites']:print(json.dumps(s))
            break
(p/'emitter-summary.json').write_text(json.dumps(out,indent=2))
