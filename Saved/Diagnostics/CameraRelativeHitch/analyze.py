import json,math,pathlib,statistics,struct,sys
root=pathlib.Path(__file__).resolve().parent
path=root/sys.argv[1] if len(sys.argv)>1 else max(root.glob('capture-[0-9]*.json'))
data=json.loads(path.read_text()); rows=data['rows']
physics=data['metadata'].get('physics',{'substepping':True,'max_substep_delta_time':struct.unpack('f',struct.pack('f',.016667))[0],'max_substeps':64})
if data['error']: raise RuntimeError(data['error'])
sub=lambda a,b:[x-y for x,y in zip(a,b)]
dot=lambda a,b:sum(x*y for x,y in zip(a,b))
norm=lambda a:math.sqrt(dot(a,a))
def camera_point(row,key):
    p,y,r=map(math.radians,row['camera_rotation']); sp,sy,sr=map(math.sin,(p,y,r)); cp,cy,cr=map(math.cos,(p,y,r))
    axes=((cp*cy,cp*sy,sp),(sr*sp*cy-cr*sy,sr*sp*sy+cr*cy,-sr*cp),(-(cr*sp*cy+sr*sy),cy*sr-cr*sp*sy,cr*cp))
    d=sub(row[key],row['camera'])
    return [dot(d,axis) for axis in axes]
for row in rows:
    row['relative']={k:camera_point(row,k) for k in ('root','target','pelvis')}
    row['error']=sub(row['pelvis'],row['target'])
    row['steps']=min(physics['max_substeps'],max(1,math.ceil(row['dt']/physics['max_substep_delta_time']))) if physics['substepping'] else 1
events=[]
for i,(a,b) in enumerate(zip(rows,rows[1:]),1):
    if b['t']<rows[0]['t']+5: continue
    speed=norm(b['mover_v']); dt=b['t']-a['t']
    if speed<20 or norm(sub(b['mover_v'],a['mover_v']))>.1: continue
    direction=[v/speed for v in b['mover_v']]
    event=dict(i=i,t=b['t'],dt=dt,previous_dt=a['dt'],steps=b['steps'],previous_steps=a['steps'],alpha=b['alpha'],
               error=b['error'],error_delta=sub(b['error'],a['error']),error_change_cm=norm(sub(b['error'],a['error'])),
               root_advance=dot(sub(b['root'],a['root']),direction),body_advance=dot(sub(b['pelvis'],a['pelvis']),direction),
               target_advance=dot(sub(b['target'],a['target']),direction),
               relative_delta={k:sub(b['relative'][k],a['relative'][k]) for k in b['relative']},
               screen_delta={k:sub(b['screen'][k],a['screen'][k]) for k in b['screen'] if b['screen'][k] and a['screen'][k]})
    event['screen_error_delta']=sub(event['screen_delta']['pelvis'],event['screen_delta']['target']) if 'pelvis' in event['screen_delta'] and 'target' in event['screen_delta'] else None
    events.append(event)
groups={}
for e in events:
    key=str(e['previous_steps'])+'->'+str(e['steps'])
    groups.setdefault(key,[]).append(e)
summary={k:dict(count=len(v),mean_error_change=statistics.mean(e['error_change_cm'] for e in v),
               max_error_change=max(e['error_change_cm'] for e in v),
               mean_error=[statistics.mean(e['error'][j] for e in v) for j in range(3)]) for k,v in groups.items()}
top=sorted(events,key=lambda x:x['error_change_cm'],reverse=True)[:20]
result=dict(source=path.name,reason=data['reason'],rows=len(rows),duration=rows[-1]['t']-rows[0]['t'],
            metadata=data['metadata'],final_settings=data.get('final_settings'),
            sample_ms_median=statistics.median(r['sample_ms'] for r in rows),sample_ms_max=max(r['sample_ms'] for r in rows),
            camera_rotation_range=[[min(r['camera_rotation'][j] for r in rows),max(r['camera_rotation'][j] for r in rows)] for j in range(3)],
            root_camera_space_range=[[min(r['relative']['root'][j] for r in rows),max(r['relative']['root'][j] for r in rows)] for j in range(3)],
            root_screen_range=[[min(r['screen']['root'][j] for r in rows if r['screen']['root']),max(r['screen']['root'][j] for r in rows if r['screen']['root'])] for j in range(2)],
            estimated_substep_groups=summary,top_tracking_jumps=top)
(root/'analysis.json').write_text(json.dumps(result,indent=2))
(root/'events.json').write_text(json.dumps(events,separators=(',',':')))
selected={str(e['t']):rows[max(0,e['i']-3):e['i']+4] for e in top[:5]}
(root/'selected-events.json').write_text(json.dumps(selected,indent=2))
print(json.dumps({**result,'top_tracking_jumps':top[:6]},indent=2))
