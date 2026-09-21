import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation
root=pathlib.Path(__file__).resolve().parents[2]
folder=root/'Saved/Diagnostics/PelvisHitch-20260920-193832'
rows={round(r['time']*60):r for r in map(json.loads,(folder/'pipeline.jsonl').read_text().splitlines()) if r['actor'].endswith('_C_1')}
metrics={r['tick']:r for r in map(json.loads,(folder/'metrics.jsonl').read_text().splitlines()) if r['agent'].endswith('_C_1')}
solve={r['tick']:r for r in json.loads((root/'Saved/Diagnostics/PelvisHitchInputs/solve_replay.json').read_text())}
off=np.array(json.loads((root/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())['local_offsets_m'])
walk=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json').read_text())
def unit(v):return v/max(1e-12,np.linalg.norm(v))
def rot(v):
    v=np.array(v);x=unit(v[:3]);y=unit(v[3:]-x*np.dot(x,v[3:]));return np.array([x,y,np.cross(x,y)])
def angle(x,y):return float(np.degrees(Rotation.from_matrix(x@y.T).magnitude()))
out=[]
for t,r in rows.items():
    if not 145<=t<=187:continue
    x=np.array(r['lower_input'][:41]);raw=x+r['lower_delta'][:41];s=np.array(r['published_lower']);prev=np.array(r['previous_lower']);m=metrics[t]
    result={'tick':t,'attack':m.get('attack'),'tempering':r.get('tempering'),'pelvis_z_cm':s[2]*100,'pin_logits':r['lower_delta'][41:43],'legs':{}}
    for i,side in enumerate(('left','right')):
        o=9+16*i;h=17+4*i
        hip=s[:3]+off[h]@rot(s[3:9]);upper=off[h+1]@rot(s[o+9:o+15]);rawupper=off[h+1]@rot(raw[o+9:o+15]);axis=unit(s[o:o+3]-hip)
        toe=unit(np.array(walk['ik_toe_offsets_m'][i]))@rot(s[o+3:o+9]);forward=unit(toe*[1,1,0]);sideaxis=np.cross([0,0,1],forward)
        oldhip=prev[:3]+off[h]@rot(prev[3:9]);oldupper=off[h+1]@rot(prev[o+9:o+15])
        p=m['bones']['foot_l' if i==0 else 'foot_r']['future']['p']
        pm=metrics[t-2]['bones']['foot_l' if i==0 else 'foot_r']['future']['p'] if t-2 in metrics else p
        result['legs'][side]={'foot_local_z_cm':s[o+2]*100,'foot_world_cm':p,'foot_world_step_cm':np.array(p).tolist() if False else float(np.linalg.norm(np.array(p)-pm)),
           'thigh_rotation_step_deg':angle(rot(x[o+9:o+15]),rot(s[o+9:o+15])),'raw_thigh_rotation_step_deg':angle(rot(x[o+9:o+15]),rot(raw[o+9:o+15])),
           'thigh_direction_step_deg':float(np.degrees(np.arccos(np.clip(np.dot(unit(oldupper),unit(upper)),-1,1)))),
           'raw_knee_from_solved_cm':float(np.linalg.norm(rawupper-upper)*100),'raw_calf_length_cm':float(np.linalg.norm(s[o:o+3]-hip-rawupper)*100),'calf_length_cm':float(np.linalg.norm(off[h+2])*100),
           'solved_knee_forward_cm':float(np.dot(upper,forward)*100),'raw_knee_forward_cm':float(np.dot(rawupper,forward)*100),'solved_knee_side_cm':float(np.dot(upper,sideaxis)*100),'raw_knee_side_cm':float(np.dot(rawupper,sideaxis)*100),
           'hip_ankle_cm':float(np.linalg.norm(s[o:o+3]-hip)*100),'geometry':solve.get(t,{}).get('legs',{}).get(side)}
    out.append(result)
    print(t,'attack',m.get('attack'),'pin',np.round(result['pin_logits'],3).tolist(),[(side,{k:round(v,3) for k,v in d.items() if isinstance(v,float)}) for side,d in result['legs'].items()])
(root/'Saved/Diagnostics/PelvisHitchInputs/planted_thigh_audit.json').write_text(json.dumps(out,indent=2))
