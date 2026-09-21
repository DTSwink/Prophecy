"""Read-only geometric attribution on recorded runtime state, no model/scene edits."""
import json,pathlib,sys,math
import numpy as np
from ReplayTemperedLeg import unit,project,rot,points,config,offsets,clean,mixstate
def degrees(x):return math.degrees(math.acos(float(np.clip(x,-1,1))))
def rotate(v,axis,angle):return v*math.cos(angle)+np.cross(axis,v)*math.sin(angle)+axis*np.dot(axis,v)*(1-math.cos(angle))
def summary(p):
    records=[];kick=0;last=False
    for line in (p/'pipeline.jsonl').open():
        r=json.loads(line)
        if r['actor']!='BP_ProphecyManualPoseAgent_C_1':continue
        if r['attack'] and not last:kick+=1
        last=r['attack']
        if last or not kick or 'tempering' not in r:continue
        s=np.array(r['published_lower']);prev=np.array(r['previous_lower']);h,k,a,t=points(s);ph,pk,pa,pt=points(prev)
        L1=np.linalg.norm(offsets[18]);L2=np.linalg.norm(offsets[19]);d=np.linalg.norm(a-h);axis=unit(a-h);u=k-h
        along=(L1*L1-L2*L2+min(d,L1+L2-2e-5)**2)/(2*min(d,L1+L2-2e-5));radius=math.sqrt(max(0,L1*L1-along*along))
        fw=unit((t-a)*[1,1,0]);side=np.cross([0,0,1],fw)
        local_up=np.array([1 if offsets[19][0]<0 else -1,0,0]);local_fw=unit(np.array(config['ik_toe_offsets_m'][0]))
        sole=unit(np.cross(local_up,local_fw))@rot(s,12);flat=sole*np.array([1,1,0]);guide_fw=unit(np.array([flat[1],-flat[0],0]))
        down=np.array([0,0,-1]);den=1-axis[2];guide=project(guide_fw-(down+axis)*np.dot(guide_fw,axis)/max(1e-6,den),axis)
        pu=pk-ph;paxis=unit(pa-ph);pole=project(pu,paxis);c=np.dot(paxis,axis)
        carried=project(-pole if c< -1+1e-6 else pole-(paxis+axis)*np.dot(pole,axis)/max(1e-6,1+c),axis)
        actual=project(u,axis)
        angle=math.atan2(np.dot(axis,np.cross(carried,guide)),np.dot(carried,guide))
        reliability=np.clip(den*4,0,1);strength=r['tempering'][1]*np.dot(flat,flat)*reliability**2*(3-2*reliability)
        predicted_pole=rotate(carried,axis,angle*strength)
        predicted_upper=axis*along+predicted_pole*radius
        toe_guide=project(fw-(down+axis)*np.dot(fw,axis)/max(1e-6,den),axis)
        source=clean(np.array(r['lower_input'][:41])+np.array(r['lower_delta'][:41]))
        if 'walk_delta' in r:source=mixstate(source,clean(np.array(r['lower_input'][:41])+np.array(r['walk_delta'][:41])),r['walk_weight'])
        sh,sk,sa,st=points(source)
        plane_amplitude=radius*np.linalg.norm(side-axis*np.dot(side,axis));plane_centre=along*np.dot(side,axis)
        row=dict(kick=kick,time=r['time'],distance_cm=d*100,ankle_delta_cm=((a-h)*100).tolist(),
            flexion_deg=degrees((d*d-L1*L1-L2*L2)/(2*L1*L2)),axis_z=axis[2],
            actual_side_cm=np.dot(u,side)*100,full_guide_side_cm=np.dot(axis*along+guide*radius,side)*100,
            toe_based_full_guide_side_cm=np.dot(axis*along+toe_guide*radius,side)*100,
            transported_side_cm=np.dot(axis*along+carried*radius,side)*100,
            min_possible_abs_side_cm=max(0,abs(plane_centre)-plane_amplitude)*100,
            guide_error_deg=degrees(np.dot(actual,guide)),heading_disagreement_deg=degrees(np.dot(fw,guide_fw)),
            replay_knee_error_cm=np.linalg.norm(predicted_upper-u)*100,
            guide_denominator=den,foot_side_horizontal_norm=np.linalg.norm(flat),
            raw_calf_error_cm=(np.linalg.norm(sa-sk)-L2)*100,
            raw_ankle_delta_cm=((sa-sh)*100).tolist(),tempering=r['tempering'],
            previous_thigh_to_current_deg=degrees(np.dot(unit(pu),unit(u))),
            source_upper_to_result_deg=degrees(np.dot(unit(sk-sh),unit(u))))
        records.append(row)
    result=dict(capture=p.name,rows=len(records),
        max_replay_knee_error_cm=max(r['replay_knee_error_cm'] for r in records),
        min_distance=min(records,key=lambda x:x['distance_cm']) if records else None,
        max_step=max(records,key=lambda x:x['previous_thigh_to_current_deg']) if records else None,
        kicks=[max([r for r in records if r['kick']==n],key=lambda r:abs(r['actual_side_cm'])) for n in sorted(set(r['kick'] for r in records))],
        infeasible_plane_samples=sum(r['min_possible_abs_side_cm']>.01 for r in records))
    (p/'mechanism-audit.json').write_text(json.dumps(dict(summary=result,frames=records),indent=2))
    print(json.dumps(result,indent=2))
if __name__=='__main__':
    for arg in sys.argv[1:]:summary(pathlib.Path(arg))
