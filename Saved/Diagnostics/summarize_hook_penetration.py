import pathlib,re,json,collections
log=pathlib.Path('Saved/Logs/GameAnimationSample3.log').read_text(encoding='utf-8',errors='replace')
current=None;runs={}
for line in log.splitlines():
    m=re.search(r'LogPython: HOOK_PENETRATION_BEGIN (\d+)',line)
    if m:current=int(m[1]);runs[current]=[];continue
    if 'LogPython: HOOK_PENETRATION_END' in line:current=None;continue
    if current is not None and 'PHAT_OVERLAP,' in line:
        fields=line.split('PHAT_OVERLAP,',1)[1].split(',')
        runs[current].append(dict(t=float(fields[0]),source=fields[1],victim=fields[2],bone=fields[3],visible=float(fields[4])))
out={}
for steps,rows in runs.items():
    if not rows:print('EMPTY',steps);continue
    bybone={}
    for bone in sorted(set(r['bone'] for r in rows)):
        bs=[r for r in rows if r['bone']==bone]
        bybone[bone]=dict(samples=len(bs),peak_visible=max(r['visible'] for r in bs),frames_positive=sum(r['visible']>.001 for r in bs),over_2cm=sum(r['visible']>2 for r in bs),worst=max(bs,key=lambda r:r['visible']))
    out[steps]=bybone
    pathlib.Path('Saved/Diagnostics/HookPenetrationDepth_'+str(steps)+'.json').write_text(json.dumps(rows))
pathlib.Path('Saved/Diagnostics/HookPenetrationSummary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
