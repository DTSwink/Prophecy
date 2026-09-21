import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation
root=pathlib.Path(__file__).resolve().parents[2]
run=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text());walk=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json').read_text())
off=np.array(run['local_offsets_m'])
def unit(v):return v/max(1e-12,np.linalg.norm(v))
def project(v,a):return unit(v-a*np.dot(v,a))
def rot(v):
    v=np.array(v);x=unit(v[:3]);y=project(v[3:],x);return np.array([x,y,np.cross(x,y)])
def angle(x,y):return float(np.degrees(Rotation.from_matrix(x@y.T).magnitude()))
def smooth(x):x=np.clip(x,0,1);return x*x*(3-2*x)
rows=[json.loads(x) for x in (root/'Saved/Diagnostics/PelvisHitch-20260920-193832/pipeline.jsonl').read_text().splitlines()]
out=[]
for r in rows:
    tick=round(r['time']*60)
    if not r['actor'].endswith('_C_1') or not 151<=tick<=177:continue
    s=np.array(r['published_lower']);prev=np.array(r['previous_lower']);raw=np.array(r['lower_input'][:41])+r['lower_delta'][:41]
    record={'tick':tick,'legs':{},'transported':{}}
    for i,side in enumerate(('left','right')):
        o=9+16*i;hidx=17+4*i;L1=np.linalg.norm(off[hidx+1]);L2=np.linalg.norm(off[hidx+2]);limit=L1+L2-2e-5
        oldr=rot(prev[o+9:o+15]);oldhip=prev[:3]+off[hidx]@rot(prev[3:9]);oldupper=off[hidx+1]@oldr
        oldaxis=unit(prev[o:o+3]-oldhip);oldpole=project(oldupper,oldaxis)
        hip=s[:3]+off[hidx]@rot(s[3:9]);end=s[o:o+3];axis=unit(end-hip)
        carried=project(oldpole-(oldaxis+axis)*np.dot(oldpole,axis)/max(1e-6,1+np.dot(oldaxis,axis)),axis)
        d=min(np.linalg.norm(end-hip),limit);along=(L1*L1-L2*L2+d*d)/(2*d);radius=np.sqrt(max(0,L1*L1-along*along))
        upper=axis*along+carried*radius
        oldn=unit(np.cross(oldaxis,oldpole));newn=unit(np.cross(axis,carried))
        oldbasis=np.array([unit(oldupper),unit(np.cross(oldn,unit(oldupper))),oldn]);newbasis=np.array([unit(upper),unit(np.cross(newn,unit(upper))),newn])
        transported=oldr@oldbasis.T@newbasis
        record['transported'][side]=transported.tolist()
        toe=unit(np.array(walk['ik_toe_offsets_m'][i]))@rot(s[o+3:o+9]);forward=unit(toe*[1,1,0]);sideaxis=np.cross([0,0,1],forward)
        radial=upper-axis*np.dot(upper,axis);R=np.linalg.norm(radial);pole=unit(radial);sidealong=np.dot(axis,sideaxis);N0=sideaxis-axis*sidealong;Nlen=np.linalg.norm(N0);N=unit(N0)
        Q=-along*sidealong/(R*Nlen);strength=smooth(np.dot(toe*[1,1,0],toe*[1,1,0])*4)*smooth(Nlen*Nlen*4)*smooth((1-abs(Q))*4)
        desired=N*np.clip(Q,-1,1)+unit(np.cross(axis,N))*np.sqrt(max(0,1-np.clip(Q,-1,1)**2))
        turn=np.arctan2(np.dot(axis,np.cross(pole,desired)),np.clip(np.dot(pole,desired),-1,1))*strength
        final=transported@Rotation.from_rotvec(axis*turn).as_matrix().T
        actual=rot(s[o+9:o+15]);record['legs'][side]={'transport_step_deg':angle(oldr,transported),'guidance_turn_deg':float(np.degrees(turn)),
            'raw_to_transport_deg':angle(rot(raw[o+9:o+15]),transported),'raw_to_final_deg':angle(rot(raw[o+9:o+15]),actual),
            'replay_error_deg':angle(final,actual),'Q':float(Q),'strength':float(strength),'hip_ankle_cm':float(d*100)}
    print(tick,{k:{n:round(v,4) for n,v in d.items()} for k,d in record['legs'].items()})
    out.append(record)
(root/'Saved/Diagnostics/PelvisHitchInputs/solve_replay.json').write_text(json.dumps(out,indent=2))
