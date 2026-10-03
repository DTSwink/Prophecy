import json,math,pathlib,sys
import numpy as np
root=pathlib.Path('Saved/Diagnostics')
def load(tag):
    data=json.loads((root/('CalfAnkleConnection-'+tag+'.json')).read_text())
    return {round(r['t']*60):r for r in data['rows'] if r['possessed']}
def points(r,kind):
    return np.array([r['meshes']['PhysicalMesh'][b]['p'] if kind=='physical' else r['targets'][b][kind]['p'] for b in ('thigh_l','calf_l','foot_l')])
def metrics(p):
    h,k,f=p;u=k-h;v=f-k;d=f-h;axis=d/np.linalg.norm(d);pole=u-axis*np.dot(u,axis)
    return {'bend':float(np.degrees(np.arccos(np.clip(np.dot(u,v)/np.linalg.norm(u)/np.linalg.norm(v),-1,1)))),
            'radius':float(np.linalg.norm(pole)),'lengths':[float(np.linalg.norm(u)),float(np.linalg.norm(v))],
            'pole':(pole/max(np.linalg.norm(pole),1.e-9)).tolist()}
a,b=map(load,sys.argv[1:3]);rows=[]
for frame in range(610,626):
    if frame not in a or frame not in b:continue
    p,q=points(a[frame],'physical'),points(b[frame],'physical')
    raw=max(np.max(np.abs(points(a[frame],'future')-points(b[frame],'future'))),np.max(np.abs(points(a[frame],'previous')-points(b[frame],'previous'))))
    row={'frame':frame,'before':metrics(p),'after':metrics(q),'foot_shift':(q[2]-p[2]).tolist(),'raw_error':float(raw)}
    rows.append(row)
    print(frame,'bend %.4f -> %.4f'%(row['before']['bend'],row['after']['bend']),'foot',np.round(q[2]-p[2],4),'raw',round(raw,7))
report={'rows':rows}
for kind in ('physical','target','future'):
    errors=[]
    for frame in a.keys()&b.keys():
        for bone in ('pelvis','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r'):
            def get(r):return r['meshes']['PhysicalMesh'][bone]['p'] if kind=='physical' else r['targets'][bone][kind]['p']
            errors.append(float(np.max(np.abs(np.array(get(a[frame]))-np.array(get(b[frame]))))))
    report[kind+'_max_difference']=max(errors)
report['source_tags']=sys.argv[1:3]
(root/('Knee617-comparison-'+sys.argv[2]+'.json')).write_text(json.dumps(report,indent=2))
print({k:v for k,v in report.items() if k!='rows'})
