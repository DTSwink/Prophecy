import pathlib,json,runpy,numpy as np
folder=pathlib.Path(__file__).parent
h=runpy.run_path(str(folder/'CompareRecoveryLegs.py'))
files={json.loads(p.read_text())['mode']:p.parent.name for p in sorted(folder.glob('PelvisHitch-*/experiment.json')) if (p.parent/'summary.json').exists()}
out=[]
for mode,capture in files.items():
    path,p,m=h['load'](capture)
    poses=h['pose_metrics'](p,149,max(m))
    for cycle in range(max(0,(max(m)-190)//120+1)):
        start=149+120*cycle;end=start+41
        dyn=h['dynamic_metrics'](m,start,end);joint=[r for r in poses if start<=r['tick']<=start+28]
        record={'mode':mode,'capture':capture,'cycle':cycle+1,'start':start,'pelvis_recovery_accel_max':dyn['pelvis']['world_second_difference_cm']['max'],
            'pelvis_hitch_accel_max':h['dynamic_metrics'](m,start+23,start+33)['pelvis']['world_second_difference_cm']['max'],
            'right_foot_accel_max':dyn['foot_r']['world_second_difference_cm']['max'],
            'legs':{}}
        for side,letter in [('left','l'),('right','r')]:
            legs=[r['legs'][side] for r in joint]
            record['legs'][side]={'max_knee_side_cm':max(abs(r['knee_side_cm']) for r in legs),'min_branch_score':min(r['oriented_hinge_branch_score'] for r in legs),
               'max_thigh_direction_step_deg':max(r['thigh_direction_step_deg'] for r in legs),'max_full_thigh_step_deg':max(r['thigh_full_step_deg'] for r in legs),
               'world_knee_accel_max':dyn['calf_'+letter]['world_second_difference_cm']['max'],'world_thigh_rotation_step_max':dyn['thigh_'+letter]['world_rotation_step_deg']['max']}
        out.append(record);print(json.dumps(record))
(folder/'PelvisHitchInputs/experiment_quality_summary.json').write_text(json.dumps(out,indent=2))
