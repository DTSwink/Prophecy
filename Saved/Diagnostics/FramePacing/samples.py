import json,pathlib,math,statistics
root=pathlib.Path(__file__).resolve().parent
path=max(root.glob('capture-*.json'))
data=json.loads(path.read_text()); rows=data['rows']; first=rows[0]['t']
events=[]
for a,b in zip(rows,rows[1:]):
    if b['t']-first<5: continue
    body_gap=math.dist(b['visible'],b['pelvis'])
    events.append({'t':b['t'],'elapsed':b['t']-first,'wall_ms':(b['wall']-a['wall'])*1000,
        'dt_ms':b['dt']*1000,'sample_ms':b['sample_ms'],'visible_body_gap_cm':body_gap,
        'visible_body_error_change_cm':math.sqrt(sum(((b['visible'][j]-b['pelvis'][j])-(a['visible'][j]-a['pelvis'][j]))**2 for j in range(3)))})
out={'source':path.name,'trace':data.get('trace_path'),'duration':rows[-1]['t']-first,'samples':len(rows),
     'max_visible_body_gap_cm':max(e['visible_body_gap_cm'] for e in events),
     'max_visible_body_error_change_cm':max(e['visible_body_error_change_cm'] for e in events),
     'over33ms':sum(e['wall_ms']>33.334 for e in events),'over25ms':sum(e['wall_ms']>25 for e in events),
     'largest_gaps':sorted(events,key=lambda e:e['wall_ms'],reverse=True)[:12]}
(root/'sample-summary.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
