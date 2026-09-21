import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation
root=pathlib.Path(__file__).resolve().parents[2]
c=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json').read_text())
offsets=np.array(c['local_offsets_m']);names=c['bone_names'] if 'bone_names' in c else c.get('joint_names')
print('names',names)
def unit(x):return x/max(1.e-12,np.linalg.norm(x))
def rot(v):
    v=np.array(v);x=unit(v[:3]);y=unit(v[3:]-x*np.dot(x,v[3:]));return np.array([x,y,np.cross(x,y)])
rows=[json.loads(x) for x in (root/'Saved/Diagnostics/PelvisHitch-20260920-193832/pipeline.jsonl').read_text().splitlines()]
out=[]
for r in rows:
    tick=round(r['time']*60)
    if not r['actor'].endswith('_C_1') or not 159<=tick<=181:continue
    raw=np.array(r['lower_input'][:41])+r['lower_delta'][:41];s=np.array(r['published_lower']);prev=np.array(r['previous_lower']);rec={'tick':tick,'legs':{}}
    for i,side in enumerate(('left','right')):
        o=9+16*i;hipindex=17+4*i;midindex=hipindex+1;endindex=hipindex+2
        L1=np.linalg.norm(offsets[midindex]);L2=np.linalg.norm(offsets[endindex])
        hip=s[:3]+offsets[hipindex]@rot(s[3:9]);ankle=s[o:o+3];axis=unit(ankle-hip)
        knee=hip+offsets[midindex]@rot(s[o+9:o+15]);forward=unit(np.array(c['ik_toe_offsets_m'][i])@rot(s[o+3:o+9]));sidevec=unit(np.cross([0,0,1],forward*[1,1,0]))
        rawhip=raw[:3]+offsets[hipindex]@rot(raw[3:9]);rawknee=rawhip+offsets[midindex]@rot(raw[o+9:o+15]);rawankle=raw[o:o+3]
        d=np.linalg.norm(ankle-hip);upper=knee-hip;radial=upper-axis*np.dot(upper,axis)
        rec['legs'][side]={'hip_ankle_cm':d*100,'max_reach_cm':(L1+L2)*100,'knee_radius_cm':np.linalg.norm(radial)*100,
            'raw_calf_length_cm':np.linalg.norm(rawankle-rawknee)*100,'authored_calf_cm':L2*100,
            'foot_forward_cm':float(np.dot(ankle-hip,unit(forward*[1,1,0]))*100),'foot_side_cm':float(np.dot(ankle-hip,sidevec)*100),
            'knee_side_cm':float(np.dot(upper,sidevec)*100),'correction_deg':float(np.degrees(Rotation.from_matrix(rot(raw[o+9:o+15])@rot(s[o+9:o+15]).T).magnitude()))}
    out.append(rec);print(tick,rec['legs'])
(root/'Saved/Diagnostics/PelvisHitchInputs/geometry.json').write_text(json.dumps(out,indent=2))
