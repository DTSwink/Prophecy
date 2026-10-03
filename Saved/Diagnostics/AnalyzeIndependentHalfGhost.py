import json,pathlib,sys,numpy as np
from scipy.spatial.transform import Rotation
root=pathlib.Path(__file__).parent/'IndependentHalfGhost'
tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'
capture=json.loads((root/(tag+'.json')).read_text());assert not capture['error'],capture['error']
traces=[json.loads(x) for x in (root/(tag+'-trace.jsonl')).read_text().splitlines()]
names=json.loads((root.parents[2]/'Content/locomotion/NN/prophecy_slash_runtime.json').read_text())['bone_names']
report={}
for family in ['hookl','slashr','headbutt','pike']:
    rows=[r for r in capture['rows'] if r['family']==family]
    steps=[r for r in traces if r['family'].lower()==family]
    if not steps:continue
    requested_error=max(np.linalg.norm(np.array(r['targets'][0])-r['targets'][2]) for r in rows)
    yaw=[];policy_target_error=[];seed_error=[];recurrence_error=[]
    for prev,cur in zip(steps,steps[1:]):
        expected=np.r_[prev['input'][41:82],prev['output'][:41],prev['input'][172:262],prev['output'][41:131]]
        recurrence_error.append(float(np.max(np.abs(expected-np.array(cur['input'][:262])))))
    for r in steps:
        native=np.array(r['native_rotation']).reshape(3,3);anchor=r['anchor'];ar=Rotation.from_quat(anchor[3:]);ap=np.array(anchor[:3]);mirror=np.diag([1,-1,1])
        out=np.array(r['output']);rot=out[206:215].reshape(3,3)@native.T
        world=ar*Rotation.from_matrix((mirror@rot@mirror).T)
        # Anatomical hip line avoids Euler yaw singularities: pelvis bone X is near vertical.
        points=out[131:206].reshape(25,3)
        hips=ar.apply(((points[names.index('thigh_r')]-points[names.index('thigh_l')])@native.T)@mirror)
        yaw.append(float(np.degrees(np.arctan2(hips[1],hips[0]))))
        policy_world=ar.apply(((np.array(r['input'][262:265])-r['native_position'])@native.T)@mirror*100)+ap
        candidates=[e for e in capture['events'] if e.get('family','').lower()==family]
        ev=candidates[0];target=ev['target']
        retarget=next((e for e in capture['events'] if e['case']==ev['case'] and 'retarget_frame' in e),None)
        if retarget and r['frame']>retarget['retarget_frame']:target=retarget['target']
        policy_target_error.append(float(np.linalg.norm(policy_world-target)))
        if r['frame']==2:
            for bone,offset in [('pelvis',41),('foot_l',50),('foot_r',66),('hand_l',232),('hand_r',247)]:
                seed_world=ar.apply(np.array(r['input'][offset:offset+3])@mirror*100)+ap
                seed_error.append(float(np.linalg.norm(seed_world-ev['pose'][bone]['p'])))
    unwrapped=np.degrees(np.unwrap(np.radians(yaw)))
    report[family]=dict(steps=len(steps),ghost_vs_requested_cm=float(requested_error),policy_target_error_cm=max(policy_target_error),seed_endpoint_error_cm=max(seed_error,default=-1),recurrence_error=max(recurrence_error,default=0),pelvis_heading_span_deg=float(np.ptp(unwrapped)),pelvis_yaw_travel_deg=float(np.abs(np.diff(unwrapped)).sum()),pelvis_yaw_net_deg=float(unwrapped[-1]-unwrapped[0]),armed=any(r['output'][431]>.5 for r in steps),hit=any(r['output'][432]>.5 for r in steps))
    if tag!='baseline':
        assert requested_error<.001,report
        assert max(policy_target_error)<.001,report
        assert max(seed_error)<.001,report
        assert max(recurrence_error,default=0)==0,report
        assert np.ptp(unwrapped)<360,report
(root/(tag+'-summary.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
