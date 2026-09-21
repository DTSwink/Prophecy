import json, pathlib, math
root=pathlib.Path(__file__).parent
def pct(xs,p):
    xs=sorted(xs)
    return round(xs[round((len(xs)-1)*p)],3) if xs else None
summary=[]
for path in sorted(root.glob('*.json')):
    if path.name=='jolt_zero_restitution-055241.json': continue # Floor native body had not been reimported in this invalid trial.
    data=json.loads(path.read_text())
    if not isinstance(data,dict) or data.get('reason')!='Complete': continue
    rows=[r for r in data['rows'] if r['actor'].endswith('_1') and r['t']>=4 and max(abs(x) for x in r['root'][:2])<7600]
    for bone in ('foot_l','foot_r'):
        vals={k:[] for k in ('error','vz','omega','lag','dvz','dvx','jerk_z')}
        peaks=[]
        for prev,r in zip(rows,rows[1:]):
            b=r['feet'][bone]; a=prev['feet'][bone]
            if b['target'][2]>=15: continue
            dt=r['t']-prev['t']
            vals['error'].append(math.dist(b['p'],b['target']))
            vals['vz'].append(abs(b['v'][2]))
            vals['omega'].append(math.sqrt(sum(x*x for x in b['w'])))
            vals['lag'].append(b['target'][0]-b['p'][0])
            vals['dvz'].append(abs(b['v'][2]-(b['target'][2]-a['target'][2])/dt))
            vals['dvx'].append(abs(b['v'][0]-(b['target'][0]-a['target'][0])/dt))
            vals['jerk_z'].append(abs(b['v'][2]-a['v'][2]))
            peaks.append((abs(b['v'][2]),round(r['t'],3)))
        s=dict(trial=path.stem,bone=bone,n=len(vals['error']),stats={k:[pct(v,.95),pct(v,1)] for k,v in vals.items()},vz_peaks=sorted(peaks,reverse=True)[:3])
        summary.append(s)
        print(json.dumps(s))
(root/'comparison.json').write_text(json.dumps(summary,indent=2))
