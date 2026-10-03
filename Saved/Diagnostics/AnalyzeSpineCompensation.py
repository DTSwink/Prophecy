import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/SpineCompensation')
captures={tag:json.loads((p/(tag+'.json')).read_text()) for tag in ['off','on']}
traces={tag:[json.loads(x) for x in (p/(tag+'-trace.jsonl')).read_text().splitlines()] for tag in captures}
for data in captures.values():assert not data['error'],data['error']
assert captures['off']['events']==captures['on']['events'],'Different entry pose or target'
a,b=captures['off']['rows'],captures['on']['rows'];assert len(a)==len(b) and a
lower=['pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r']
assert [r for r in a if not r['half']]==[r for r in b if not r['half']],'Full attacks changed'
for x,y in zip(a,b):
    assert (x['family'],x['frame'],x['targets'])==(y['family'],y['frame'],y['targets'])
    assert all(x['pose'][bone]==y['pose'][bone] for bone in lower),'Lower body changed'
    assert x['pose']['spine_01']['p']==y['pose']['spine_01']['p'],'Spine attachment moved'
assert len(traces['off'])==len(traces['on'])
for x,y in zip(traces['off'],traces['on']):
    assert (x['family'],x['frame'],x['input'],x['output'],x['anchor'])==(y['family'],y['frame'],y['input'],y['output'],y['anchor']),'Independent ghost changed'
mirror=np.diag([1,-1,1]);errors={}
for tag in captures:
    indexed={(r['family'].lower(),r['frame']):r for r in traces[tag]}
    angles=[]
    for row in captures[tag]['rows']:
        step=indexed.get((row['family'],row['frame']))
        if not row['half'] or not step:continue
        native=np.array(step['native_rotation']).reshape(3,3)
        rotation=np.array(step['output'][215:224]).reshape(3,3)@native.T
        ghost=R.from_quat(step['anchor'][3:])*R.from_matrix((mirror@rotation@mirror).T)
        visible=R.from_quat(row['pose']['spine_01']['q'])
        angles.append(float(np.degrees((ghost.inv()*visible).magnitude())))
    assert angles
    errors[tag]=dict(samples=len(angles),max_spine_world_rotation_error_deg=max(angles))
assert errors['off']['max_spine_world_rotation_error_deg']>1,'Fixture did not exercise rotation mismatch'
assert errors['on']['max_spine_world_rotation_error_deg']<.001,errors
report=dict(samples=len(a),full_samples=sum(not r['half'] for r in a),half_samples=sum(r['half'] for r in a),ghost_steps=len(traces['off']),full_unchanged=True,lower_unchanged=True,spine_attachment_unchanged=True,ghost_and_retarget_unchanged=True,orientation=errors)
if (p/'distributed.json').exists():
    distributed=json.loads((p/'distributed.json').read_text());assert not distributed['error'],distributed['error']
    dt=[json.loads(x) for x in (p/'distributed-trace.jsonl').read_text().splitlines()]
    assert len(dt)==len(traces['off'])
    for x,y in zip(traces['off'],dt):
        assert (x['family'],x['frame'],x['input'],x['output'],x['anchor'])==(y['family'],y['frame'],y['input'],y['output'],y['anchor'])
    assert len(a)==len(distributed['rows'])
    assert [r for r in a if not r['half']]==[r for r in distributed['rows'] if not r['half']]
    indexed={(r['family'].lower(),r['frame']):r for r in dt}
    distributed_errors=[[] for _ in range(5)];length_errors=[]
    for off,row in zip(a,distributed['rows']):
        assert off['targets']==row['targets']
        assert all(off['pose'][bone]==row['pose'][bone] for bone in lower)
        assert np.linalg.norm(np.array(off['pose']['spine_01']['p'])-row['pose']['spine_01']['p'])<1.e-8
        step=indexed.get((row['family'],row['frame']))
        if not row['half'] or not step:continue
        native=np.array(step['native_rotation']).reshape(3,3)
        rotation=np.array(step['output'][251:260]).reshape(3,3)@native.T
        ghost_chest=R.from_quat(step['anchor'][3:])*R.from_matrix((mirror@rotation@mirror).T)
        counter=ghost_chest*R.from_quat(off['pose']['spine_05']['q']).inv()
        for i in range(5):
            name='spine_0'+str(i+1);parent='pelvis' if i==0 else 'spine_0'+str(i)
            expected=R.from_rotvec(counter.as_rotvec()*((i+1)/5))*R.from_quat(off['pose'][name]['q'])
            actual=R.from_quat(row['pose'][name]['q'])
            distributed_errors[i].append(float(np.degrees((expected.inv()*actual).magnitude())))
            local=[]
            for r in [off,row]:
                local.append(R.from_quat(r['pose'][parent]['q']).inv().apply(np.array(r['pose'][name]['p'])-r['pose'][parent]['p']))
            length_errors.append(float(np.linalg.norm(local[0]-local[1])))
    maxes=[max(v) for v in distributed_errors]
    assert max(maxes)<.001,maxes
    assert max(length_errors)<.0001,max(length_errors)
    report['distributed']=dict(samples=len(distributed_errors[0]),max_fractional_rotation_error_deg=maxes,max_local_attachment_error_cm=max(length_errors),full_lower_ghost_retarget_unchanged=True)
(p/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
