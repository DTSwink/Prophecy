import json,pathlib,numpy as np
p=pathlib.Path('Saved/Diagnostics/KinematicFlicker')
a=json.loads((p/'before.json').read_text());b=json.loads((p/'after.json').read_text())
assert not a['error'] and not b['error'],(a['error'],b['error'])
assert len(a['rows'])==len(b['rows'])
report={}
for tag,data in [('before',a),('after',b)]:
    rows=data['rows'];samples=[]
    for r in rows:
        debug=r['meshes']['KinematicDebugMesh_0']['bones']
        error={bone:float(np.linalg.norm(np.array(v['p'])-r['pose'][bone]['presented']['p'])) for bone,v in debug.items() if bone in r['pose']}
        samples.append(dict(tick=r['tick'],max_error_cm=max(error.values()),pelvis_error_cm=error['pelvis']))
    report[tag]=dict(max_error_cm=max(x['max_error_cm'] for x in samples),samples=[x for x in samples if 137<=x['tick']<=141])
report['authored_max_change_cm']=max(float(np.linalg.norm(np.array(x['pose'][bone]['presented']['p'])-y['pose'][bone]['presented']['p'])) for x,y in zip(a['rows'],b['rows']) for bone in x['pose'])
report['physical_max_change_cm']=max(float(np.linalg.norm(np.array(x['meshes']['PhysicalMesh']['bones'][bone]['p'])-y['meshes']['PhysicalMesh']['bones'][bone]['p'])) for x,y in zip(a['rows'],b['rows']) for bone in x['meshes']['PhysicalMesh']['bones'])
(p/'summary.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
assert report['after']['max_error_cm']<.001,'Debug skeleton still leaves the presented pose'
assert report['authored_max_change_cm']<.001 and report['physical_max_change_cm']<.001,'Visual-only fix affected motion'
