import json, math, pathlib
root=pathlib.Path(__file__).resolve().parent
path=max(root.glob('continuous-[0-9]*.json'))
data=json.loads(path.read_text())
rows=data['rows']
frames=[]
for a,b in zip(rows,rows[1:]):
    if b['t']<rows[0]['t']+5: continue
    speed=math.hypot(*b['mover_v'][:2])
    if speed<20 or math.dist(a['mover_v'],b['mover_v'])>.1: continue
    dt=b['t']-a['t']
    direction=[v/speed for v in b['mover_v'][:2]]
    keys=['capsule','target','future','body']
    if 'camera' in a and 'camera' in b: keys.append('camera')
    delta={k:sum((b[k][j]-a[k][j])*direction[j] for j in range(2)) for k in keys}
    frames.append(dict(t=b['t'],dt=dt,previous_dt=a['dt'],alpha=b['alpha'],previous_alpha=a['alpha'],
        **delta,root_ratio=delta['capsule']/(speed*dt),target_ratio=delta['target']/(speed*dt),
        body_relative_root=delta['body']-delta['capsule'],
        body_relative_camera=delta['body']-delta.get('camera',delta['capsule'])))
recovery=[x for x in frames if x['previous_dt']>=1/30 and x['dt']<1/30]
result=dict(source=path.name,rows=len(rows),steady_frames=len(frames),duration=rows[-1]['t']-rows[0]['t'],
    error=data['error'],injections=len(data['injections']),settings_modified=data['settings_modified'],
    final_settings=data.get('final_settings'),
    maximum_root_speed_relative_error=max(abs(x['root_ratio']-1) for x in frames),
    minimum_target_speed_ratio=min(x['target_ratio'] for x in frames),
    minimum_body_advance_cm=min(x['body'] for x in frames),
    maximum_body_relative_root_step_cm=max(abs(x['body_relative_root']) for x in frames),
    maximum_body_relative_camera_step_cm=max(abs(x['body_relative_camera']) for x in frames),
    recovery_frames=recovery,
    root_speed_failures=[x for x in frames if abs(x['root_ratio']-1)>.005],
    target_stops_or_reversals=[x for x in frames if x['target_ratio']<.05],
    body_backward_events=[x for x in frames if x['body']<-.01])
(root/'continuous-analysis.json').write_text(json.dumps(result,indent=2))
print(json.dumps({**result,'recovery_frames':len(recovery)},indent=2))
assert data['error'] is None and data['reason']=='Duration complete'
assert len(data['injections'])==24 and len(recovery)>=12
assert not result['root_speed_failures'] and not result['target_stops_or_reversals'] and not result['body_backward_events']
