"""Check debug control-bone positions and the Blueprint root window against recorded input tensors."""
import json, math
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[2]
directory=root/'Saved/Diagnostics/SlashContacts'
capture=json.loads((directory/'InputDebugClamps.json').read_text())
assert capture['reason']=='Complete',capture['reason']
traces=[json.loads(line) for line in (directory/'nn_inputs.jsonl').read_text().splitlines()]
contract=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())
seed=np.array(contract['seed_root_rotation_rows'])
errors=[];root_errors=[];yaw_errors=[]
def yaw(a):return np.array([[math.cos(a),0,-math.sin(a)],[0,1,0],[math.sin(a),0,math.cos(a)]])
for row in capture['rows']:
    if row['t']<0.2:continue
    trace=max((r for r in traces if r['actor']==row['actor'] and r['time']<=row['t']+1e-6),key=lambda r:r['time'])
    li,ui=trace['lower_input'],trace['upper_input']
    for bone,start in [('pelvis',0),('foot_l',9),('foot_r',25),('hand_l',60),('hand_r',75)]:
        point=np.array(li[41+start:44+start]) if start<41 else np.array(ui[start:start+3])@seed.T
        expected=point*np.array([100,-100,100])
        errors.append(float(np.linalg.norm(expected-row['debug'][bone])))
    origin=np.array(trace['roots'][:3]);angle=trace['roots'][3]
    previous_angle=angle-li[119]*contract['max_turn_rate_scale_final']
    previous_origin=origin-np.array([li[117],0,li[118]])*contract['max_speed_scale_final']@yaw(previous_angle)
    expected=[(previous_origin,previous_angle),(origin,angle)]
    for index in range(8):
        start=120+index*4
        local=np.array([li[start],0,li[start+1]])*(index+1)*contract['max_speed_scale_final']
        expected.append((origin+local@yaw(angle),angle+math.atan2(li[start+3],li[start+2])))
    for (p,a),value in zip(expected,row['roots']):
        root_errors.append(float(np.linalg.norm(p[[0,2,1]]*100-value[:3])))
        quat=np.array([0,0,math.sin(-a/2),math.cos(-a/2)])
        yaw_errors.append(1-abs(float(quat@np.array(value[3:]))))
assert max(errors)<0.001,max(errors)
assert max(root_errors)<0.001,max(root_errors)
assert max(yaw_errors)<1e-6,max(yaw_errors)
summary=dict(passed=True,samples=len(errors),max_debug_position_error_cm=max(errors),max_root_position_error_cm=max(root_errors),max_quaternion_dot_error=max(yaw_errors))
(directory/'InputDebugValidation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(summary)
