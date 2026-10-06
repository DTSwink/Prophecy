import pathlib,json
p=pathlib.Path(__file__).parent
d=json.loads((p/'after.json').read_text());h=json.loads((p/'after-hits.json').read_text())
assert d['reason']=='complete',d['reason']
assert not d['errors'],d['errors']
clock={round(r['time'],5):r['tick'] for r in d['rows']}
ev=[dict(x,absolute_tick=clock.get(round(x['time'],5))) for x in h['contacts'] if x['not_self'] and x['active']]
players=[r for r in d['rows'] if r['player']]
out={'reason':d['reason'],'player_attacks':list(dict.fromkeys(r['attack'][0] for r in players if r['attack'])),'first_actual_hit_absolute_tick':min(x['absolute_tick'] for x in ev),'first_actual_hits':ev[:4],'sweep_states':list(dict.fromkeys((r['attack'][0] if r['attack'] else 'idle',r['sweeps']) for r in players))}
(p/'analysis.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
