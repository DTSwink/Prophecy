import json,pathlib,time,datetime,re
root=pathlib.Path(__file__).resolve().parent
data=json.loads((root/'capture-120539.json').read_text())
rows=data['rows']
index=max(range(1,len(rows)),key=lambda i: rows[i]['wall']-rows[i-1]['wall'] if rows[i]['t']>5 else 0)
offset=time.time()-time.perf_counter()
when=datetime.datetime.fromtimestamp(rows[index]['wall']+offset,datetime.timezone.utc)
print('Largest gap sample UTC:',when.isoformat())
print(json.dumps([{k:r[k] for k in ('t','wall','dt','sample_ms')} for r in rows[index-2:index+3]],indent=2))
log=(root.parents[2]/'Saved/JoltMigration/RuntimeSelfCollision-20260910/Editor.log').read_text(errors='replace')
selected=[]
for line in log.splitlines():
    m=re.match(r'\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3})\]',line)
    if not m: continue
    timestamp=datetime.datetime.strptime(m[1],'%Y.%m.%d-%H.%M.%S:%f').replace(tzinfo=datetime.timezone.utc)
    if abs((timestamp-when).total_seconds())<.4: selected.append(line)
(root/'frame-gap-log.txt').write_text('\n'.join(selected))
print('\n'.join(line for line in selected if 'LogBlueprintUserMessages' not in line))
