import json,pathlib,statistics
root=pathlib.Path(__file__).resolve().parent
report={}
for label,path in [('before','baseline-events.json'),('after','events.json')]:
    all_events=json.loads((root/path).read_text())
    report[label]={}
    for start in [5,20,30]:
        events=[e for e in all_events if e['t']>=start]
        axes={}
        for axis in range(3):
            values=sorted(abs(e['error_delta'][axis]) for e in events)
            axes['xyz'[axis]]={'mean':statistics.mean(values),'p99':values[int(.99*(len(values)-1))],'max':max(values)}
        report[label][start]={'n':len(events),'error_delta_cm':axes,
            'minimum_body_advance_cm':min(e['body_advance'] for e in events),
            'max_screen_tracking_delta_px':[max(abs(e['screen_error_delta'][j]) for e in events if e['screen_error_delta']) for j in range(2)]}
(root/'comparison.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
