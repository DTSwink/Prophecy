import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation
root=pathlib.Path(__file__).parent/'HalfPelvisMount'
capture=json.loads((root/'live.json').read_text());assert not capture['error'],capture['error']
traces=[json.loads(x) for x in (root/'trace.jsonl').read_text().splitlines()]
names=json.loads((root.parents[2]/'Content/locomotion/NN/prophecy_slash_runtime.json').read_text())['bone_names']
mirror=np.diag([1,-1,1]);errors=[];angles=[];pelvis_rots=[];cases={}
for trace in traces:
    rows=[x for x in capture['rows'] if x['frame']==trace['frame'] and x['family']==trace['family'].lower() and abs(x['t']-trace['time'])<.001]
    if not rows:continue
    row=rows[0];assert row['half']
    raw=np.asarray(trace['output']);p=raw[131:206].reshape(25,3);r=raw[206:431].reshape(25,3,3)
    # Relative rotations/positions cancel the fixed native carrier and ghost anchor.
    expected_r=(mirror @ r @ np.transpose(r[0]) @ mirror).transpose(0,2,1)
    expected_p=(p-p[0]) @ r[0].T @ mirror*100
    real=row['pose'];base=real['pelvis'];br=Rotation.from_quat(base['q']);bp=np.array(base['p'])
    pelvis_rots.append(br.as_rotvec().tolist())
    for bone in ['spine_01','spine_02','spine_03','spine_04','spine_05','neck_01','neck_02','head','clavicle_l','clavicle_r']:
        index=names.index(bone);b=real[bone]
        actual_r=br.inv()*Rotation.from_quat(b['q']);actual_p=br.inv().apply(np.array(b['p'])-bp)
        errors.append(float(np.linalg.norm(actual_p-expected_p[index])))
        angles.append(float(np.degrees((actual_r.inv()*Rotation.from_matrix(expected_r[index])).magnitude())))
    cases[row['family']]=cases.get(row['family'],0)+1
assert len(cases)==4 and min(cases.values())>1,cases
report=dict(policy_samples=cases,max_upper_relative_position_cm=max(errors),max_upper_relative_rotation_deg=max(angles),events=capture['events'])
(root/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
assert max(errors)<.01 and max(angles)<.01,report
