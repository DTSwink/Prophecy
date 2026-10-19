"""Read-only check of recorded position loss against actual captured targets."""
import json
import sys
from pathlib import Path
import numpy as np

p=Path(sys.argv[1])
with np.load(p/'replay.npz') as z:
    meta=json.loads(str(z['metadata']))
    reports=[]
    for i,row in enumerate(meta.get('replay_rows',[meta])):
        suffix='' if i==0 else '_'+str(i)
        pose=z['pose'+suffix][1:,:,:3]
        target=z['reference_pose'+suffix][1:,:,:3]
        d=pose-target
        cfg=row['position_mse_leeway']
        legs=np.array([n in cfg['leg_bodies'] for n in row['names']])
        assert legs.sum()==6 and cfg['axes']=='world_xy_horizontal_z_vertical'
        leg=np.maximum(np.linalg.norm(d[...,:2],axis=-1)-cfg['leg_horizontal_radius_m'],0)**2
        leg+=np.maximum(abs(d[...,2])-cfg['leg_vertical_half_height_m'],0)**2
        upper=np.maximum(np.linalg.norm(d,axis=-1)-cfg['other_radius_m'],0)**2
        expected=np.where(legs,leg,upper).mean(-1)/3*row['loss_weights']['position_mse']
        active=cfg.get('scope','all')!='idle' or row['idle_row']
        if not active:
            radius=cfg.get('locomotion_radius_m',0.)
            expected=np.square(np.maximum(np.linalg.norm(d,axis=-1)-radius,0)).mean(-1)/3*row['loss_weights']['position_mse']
        actual=z['loss_terms'+suffix][1:,row['loss_term_names'].index('position_mse')]
        np.testing.assert_allclose(actual,expected,rtol=3e-5,atol=3e-6)
        reports.append(dict(row=i,idle_row=row.get('idle_row'),idle_allowance_active=active,
            locomotion_radius_m=0. if active else cfg.get('locomotion_radius_m',0.),
            ticks=len(actual),max_difference=float(np.max(abs(actual-expected))) if len(actual) else 0.))
    report=dict(iteration=meta['iteration'],samples=meta['samples'],rows=reports,
        passed=True,position_mse_leeway=meta['position_mse_leeway'])
    print(json.dumps(report))
