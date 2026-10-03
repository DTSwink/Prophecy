import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics/AttackFootSink')
base=json.loads((p/'baseline.json').read_text());late=json.loads((p/'late.json').read_text())
assert not base['error'] and not late['error'],(base['error'],late['error'])
a={r['frame']:r for r in base['rows']};b={r['frame']:r for r in late['rows']}
def physical(r,bone):return np.array(r['physical'][bone]['transform']['p'])
prefix=max(float(np.max(np.abs(physical(a[f],bone)-physical(b[f],bone)))) for f in range(1,120) for bone in a[f]['physical'])
report=dict(prefix_max_cm=prefix,events=base['events'],feet={})
for bone in ('foot_l','foot_r'):
    result={}
    for tag,rows in [('baseline',a),('late',b)]:
        pre=float(np.mean([physical(rows[f],bone)[2] for f in range(100,120)]))
        points=[physical(rows[f],bone)[2] for f in range(120,133)]
        result[tag]=dict(before_z_cm=pre,min_z_cm=float(min(points)),drop_cm=pre-float(min(points)))
    result['first_step_authored_delta_cm']=float(np.linalg.norm(np.array(a[120]['authored'][bone]['p'])-b[120]['authored'][bone]['p']))
    result['samples']=[dict(frame=f,state=a[f]['state'],authored_z=a[f]['authored'][bone]['p'][2],baseline_z=physical(a[f],bone)[2],late_z=physical(b[f],bone)[2]) for f in [119,120,121,122,125,130,140,150,155,160]]
    report['feet'][bone]=result
(p/'summary.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
