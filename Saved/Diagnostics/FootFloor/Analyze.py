import json, pathlib, math, statistics
root=pathlib.Path(__file__).parent
def percentile(xs,p):
    xs=sorted(xs)
    return xs[round((len(xs)-1)*p)] if xs else None
for path in sorted(root.glob('*-*.json')):
    if path.name.startswith('scene'): continue
    data=json.loads(path.read_text())
    if 'rows' not in data: continue
    print('\n',path.name,'reason',data.get('reason'),'error',data.get('error'),'metadata',data.get('metadata'))
    grouped={}
    for row in data['rows']:
        if abs(row['root'][0])>7600 or abs(row['root'][1])>7600: continue
        for bone,b in row['feet'].items():
            if bone.startswith('ball'): continue
            grouped.setdefault((row['actor'],bone),[]).append((row,b))
    for key,rows in grouped.items():
        errors=[math.dist(b['p'],b['target']) for r,b in rows]
        close=[(r,b) for r,b in rows if b['target'][2]<15]
        vz=[abs(b['v'][2]) for r,b in close]
        lag=[b['target'][0]-b['p'][0] for r,b in close]
        stats={'n':len(rows),'close_n':len(close),'t0':rows[0][0]['t'],'t1':rows[-1][0]['t'],
            'error_p50_p95_max':[percentile(errors,p) for p in (.5,.95,1)],
            'near_ground_abs_vz_p50_p95_max':[percentile(vz,p) for p in (.5,.95,1)],
            'near_ground_lag_x_p50_p95_max':[percentile(lag,p) for p in (.5,.95,1)],
            'z_p01_p50_p99':[percentile([b['p'][2] for r,b in rows],p) for p in (.01,.5,.99)]}
        print(key,json.dumps(stats))
