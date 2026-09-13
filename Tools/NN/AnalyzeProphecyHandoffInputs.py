"""Validate recorded NN handoff histories against outgoing world poses, without rendering."""
import json
import math
from pathlib import Path
import numpy as np

root=Path(__file__).resolve().parents[2]
directory=root/'Saved/Diagnostics/SlashContacts'
traces=[json.loads(line) for line in (directory/'HandoffInputs.jsonl').read_text().splitlines()]
capture=json.loads((directory/'LocomotionHandoff.json').read_text())
assert capture['reason']=='Complete',capture['reason']
poses=capture['rows']
lower=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())
upper=json.loads((root/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
seed=np.array(lower['seed_root_rotation_rows'])
def yaw(value):
    c,s=math.cos(value),math.sin(value)
    return np.array([[c,0,-s],[0,1,0],[s,0,c]])
def matrix(values):
    a=np.array(values[:3]);a/=np.linalg.norm(a)
    b=np.array(values[3:6]);b-=a*np.dot(a,b);b/=np.linalg.norm(b)
    return np.array([a,b,np.cross(a,b)])
def base(values,offset):
    return np.array(values[offset:offset+3]),matrix(values[offset+3:offset+9])
def world(position,origin,angle):return (origin+position@yaw(angle))[[0,2,1]]*100
results=[]
for name in sorted({p['actor'] for p in poses}):
    actor_rows=[r for r in traces if r['actor']==name]
    for before,row in zip(actor_rows,actor_rows[1:]):
        if not (before['attack'] and not row['attack']):continue
        origin=np.array(row['roots'][:3]);angle=row['roots'][3]
        li,ui=row['lower_input'],row['upper_input']
        previous_angle=angle-li[119]*lower['max_turn_rate_scale_final']
        previous_origin=origin-np.array([li[117],0,li[118]])*lower['max_speed_scale_final']@yaw(previous_angle)
        result=dict(actor=name,time=row['time'],half=row['half'],errors_cm={})
        for mode,dt in [('current',1/30),('previous',2/30)]:
            expected=max((p for p in poses if p['actor']==name and p['t']<=row['time']-dt+1e-5),key=lambda p:p['t'])
            errors={}
            offset=0 if mode=='current' else 41
            source_origin,source_angle=(origin,angle) if mode=='current' else (previous_origin,previous_angle)
            for bone,start in [('pelvis',0),('foot_l',9),('foot_r',25)]:
                point=np.array(li[offset+start:offset+start+3])@seed
                errors[bone]=float(np.linalg.norm(world(point,source_origin,source_angle)-expected['future'][bone][:3]))
            for side,start in [('l',60),('r',75)]:
                if mode=='previous':point=np.array(ui[start:start+3])
                else:
                    # Undo the training-defined pelvis baseline transport of the prior.
                    cp,cr=base(ui,189);np_,nr=base(ui,198)
                    rest=np.array(upper['rest_offsets_from_pelvis_m'][upper['body_names'].index('hand_'+side)])
                    point=np.array(ui[90+start:93+start])-(np_+rest@nr)+(cp+rest@cr)
                errors['hand_'+side]=float(np.linalg.norm(world(point,source_origin,source_angle)-expected['future']['hand_'+side][:3]))
            assert max(errors.values())<0.0001,(name,row['time'],mode,errors)
            result['errors_cm'][mode]=errors
        results.append(result)
assert len(results)>=4 and {r['half'] for r in results}=={False,True}
summary=dict(passed=True,exits=results,max_history_error_cm=max(v for r in results for mode in r['errors_cm'].values() for v in mode.values()),stop_pose_errors=capture['events'])
(directory/'HandoffInputValidation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print('Handoff history validation:',len(results),'exits, maximum',summary['max_history_error_cm'],'cm')
