import json,pathlib,sys,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/PositionCompensation');tags=sys.argv[1:] or ['current']
mirror=np.diag([1,-1,1]);bone_names=json.loads(pathlib.Path('Content/locomotion/NN/prophecy_slash_runtime.json').read_text())['bone_names']
report={}
for tag in tags:
    data=json.loads((p/(tag+'.json')).read_text());assert not data['error'],data['error']
    steps=[json.loads(s) for s in (p/(tag+'-trace.jsonl')).read_text().splitlines()]
    rows=[]
    for row in data['rows']:
        state=row['state']
        if not state or not state[1]:continue
        eligible=[s for s in steps if s['family'].lower()==state[0].lower() and s['frame']==state[-1] and s['time']<=row['t']+1.e-6]
        if not eligible:continue
        step=eligible[-1];native=np.array(step['native_rotation']).reshape(3,3);anchor=R.from_quat(step['anchor'][3:]);target=np.array(row['targets'][0]);pose=dict(zip(row['names'],row['future']))
        def ghost(name):
            i=bone_names.index(name);out=np.array(step['output']);pos=(out[131+3*i:134+3*i]-step['native_position'])@native.T
            pos=anchor.apply(pos@mirror*100)+step['anchor'][:3]
            rot=out[206+9*i:215+9*i].reshape(3,3)@native.T
            return pos,anchor*R.from_matrix((mirror@rot@mirror).T)
        gp,gr=ghost('spine_05');real=np.array(pose['spine_05'][:3]);rr=R.from_quat(pose['spine_05'][3:]);pivot=np.array(pose['spine_01'][:3])
        virtual=real+rr.apply(gr.inv().apply(target-gp));v=virtual-pivot;t=target-pivot
        angle=float(np.degrees(np.arctan2(np.linalg.norm(np.cross(v,t)),np.dot(v,t))))
        rows.append(dict(frame=row['frame'],attack_frame=state[-1],hit=state[3],proxy_miss_cm=float(np.linalg.norm(virtual-target)),angle_deg=angle,pelvis_translation_cm=float(np.linalg.norm(np.array(pose['pelvis'][:3])-ghost('pelvis')[0])),ghost_hand_distance_cm=float(np.linalg.norm(ghost('hand_r')[0]-target)),real_hand_distance_cm=float(np.linalg.norm(np.array(pose['hand_r'][:3])-target))))
    assert rows,tag+' did not exercise half attacks'
    report[tag]=dict(samples=len(rows),mean_proxy_miss_cm=float(np.mean([r['proxy_miss_cm'] for r in rows])),max_proxy_miss_cm=max(r['proxy_miss_cm'] for r in rows),max_aim_error_deg=max(r['angle_deg'] for r in rows),rows=rows)
    print(tag,{k:v for k,v in report[tag].items() if k!='rows'});print('hit',[(r['frame'],round(r['proxy_miss_cm'],3),round(r['angle_deg'],4)) for r in rows if r['hit']])
(p/'summary.json').write_text(json.dumps(report,indent=2))
