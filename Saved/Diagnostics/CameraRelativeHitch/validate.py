import json,pathlib,math
root=pathlib.Path(__file__).resolve().parent
analysis=json.loads((root/'analysis.json').read_text())
events=json.loads((root/'events.json').read_text())
capture=json.loads((root/analysis['source']).read_text())
assert analysis['reason']=='Duration complete' and analysis['duration']>=65
assert abs(analysis['metadata']['physics']['max_substep_delta_time']-.01)<1.e-8
worst=max(e['error_change_cm'] for e in events)
screen=max(math.hypot(*e['screen_error_delta']) for e in events if e['screen_error_delta'])
assert worst<.1, worst
assert screen<.25, screen
assert all(e['body_advance']>0 and e['root_advance']>0 and e['target_advance']>0 for e in events)
old=json.loads((root/'baseline-events.json').read_text())
assert max(e['error_change_cm'] for e in old)>.9
rows=capture['rows']
gaps=sorted([{'t':b['t'],'world_ms':b['dt']*1000,'wall_ms':(b['wall']-a['wall'])*1000}
             for a,b in zip(rows,rows[1:]) if b['t']>5],key=lambda e:e['wall_ms'],reverse=True)
result={'source':analysis['source'],'duration':analysis['duration'],'steady_frames':len(events),
    'max_tracking_jump_cm':worst,'max_screen_tracking_jump_px':screen,
    'frames_after_20_seconds':sum(e['t']>=20 for e in events),'largest_frame_gaps':gaps[:5],
    'frame_gaps_over_33ms':sum(e['wall_ms']>33.334 for e in gaps)}
(root/'validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
