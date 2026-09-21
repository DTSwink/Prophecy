import json,pathlib
root=pathlib.Path(__file__).parent
rs=json.loads((root/'PelvisHitchInputs/experiment_quality_summary.json').read_text())
print('mode cycle hitchAccel leftSide rightSide leftThighStep rightThighStep rightFootAccel')
for r in rs:
    if r['mode']<3 and r['mode']!=0:continue
    print(r['mode'],r['cycle'],*[round(x,3) for x in [r['pelvis_hitch_accel_max'],r['legs']['left']['max_knee_side_cm'],r['legs']['right']['max_knee_side_cm'],r['legs']['left']['max_full_thigh_step_deg'],r['legs']['right']['max_full_thigh_step_deg'],r['right_foot_accel_max']]])
