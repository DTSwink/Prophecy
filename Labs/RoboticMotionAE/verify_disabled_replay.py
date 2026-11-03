"""Independent reconstruction from recorded poses/velocities, not environment code."""
import json,sys
import numpy as np

def verify(path):
    checks=[]
    with np.load(path,allow_pickle=False) as z:
        meta=json.loads(str(z['metadata']))
        for i,row in enumerate(meta['replay_rows']):
            suffix='' if i==0 else '_'+str(i)
            pose=z['pose'+suffix][1:].astype(np.float64);target=z['reference_pose'+suffix][1:].astype(np.float64)
            velocities=z['world_velocities'+suffix][1:].astype(np.float64)
            data=z['data'+suffix][1:];terms=z['loss_terms'+suffix][1:]
            enabled=np.array([n not in row['excluded_mse_bodies'] for n in row['names']])
            position=(((pose[:,:,:3]-target[:,:,:3])**2)*enabled[None,:,None]).mean((1,2))*row['loss_weights']['position_mse']
            aq=pose[:,:,3:];tq=target[:,:,3:]
            dot=np.abs((aq*tq).sum(-1)/(np.linalg.norm(aq,axis=-1)*np.linalg.norm(tq,axis=-1)))
            rotation=(8*(1-np.clip(dot,0,1)**2)*enabled[None]).mean(-1)/9*row['loss_weights']['rotation_mse']
            weights=enabled.astype(float);weights[row['names'].index('head')]*=3.
            for name in row['active_leg_velocity_mse']['affected_bodies_by_motion'].get(row['motion_name'],[]):weights[row['names'].index(name)]*=5.
            expected=[position,None,rotation,None];error={}
            for column,actual,reference,key in [(1,0,6,'linear_velocity_mse'),(3,3,9,'angular_velocity_mse')]:
                expected[column]=(((velocities[:,:,actual:actual+3]-velocities[:,:,reference:reference+3])**2)*weights[None,:,None]).mean((1,2))*row['loss_weights'][key]
            for column,prediction in enumerate(expected):
                assert np.allclose(prediction,terms[:,column],atol=5e-5,rtol=3e-4),(row['replay_row_label'],column,float(np.max(abs(prediction-terms[:,column]))))
                error[row['loss_term_names'][column]]=float(np.max(abs(prediction-terms[:,column])))
            columns=[j for j,n in enumerate(row['loss_term_names']) if n!='auto_phase']
            expected_reward=np.exp(-terms[:,columns].sum(-1))-row['loco_failure_penalty']*(data[:,0]==1)
            if 'crawl_forward_reward' in row:
                spec=row['crawl_forward_reward']
                active=row['motion_name']=='crawl' and row['disabled_limb_code']==12 and row['cohort_index']>0
                if row.get('crawl_jiggle_penalty',{}).get('enabled',False):
                    assert not spec['enabled']
                    active=False
                else:assert spec['enabled']==active and spec['maximum']==5.
                target=np.asarray(spec['target_velocity_xy_m_s'])
                velocity=velocities[:,row['names'].index('pelvis'),:2]
                if spec.get('form')=='signed_displacement_v1':
                    xy=z['pose'+suffix][:,row['names'].index('pelvis'),:2].astype(np.float64)
                    velocity=np.diff(xy,axis=0)*float(row['fps'])
                    bonus=5.*(1.-np.sqrt(((velocity-target)**2).sum(-1))/np.linalg.norm(target)) if active else np.zeros(len(data))
                else:
                    bonus=5.*np.maximum(0.,1.-np.sqrt(((velocity-target)**2).sum(-1))/np.linalg.norm(target)) if active else np.zeros(len(data))
                assert np.allclose(bonus,np.asarray(row['frame_crawl_forward_reward'])[1:],atol=2e-5)
                expected_reward+=bonus
            if 'crawl_jiggle_penalty' in row:
                from crawl_jiggle import recorded_cost
                spec=row['crawl_jiggle_penalty']
                cost=recorded_cost(z['pose'+suffix].astype(np.float64),[row['names'].index(n) for n in spec['bodies']],row['names'].index('pelvis'),float(row['fps']))
                if not spec['enabled']:cost[:]=0.
                assert np.allclose(cost,np.asarray(row['frame_crawl_jiggle_penalty']),atol=2e-4,rtol=2e-4)
                expected_reward-=cost[1:]
            assert np.allclose(expected_reward,data[:,2],atol=2e-4,rtol=2e-4),(row['replay_row_label'],float(np.max(abs(expected_reward-data[:,2]))))
            if 'crawl_jiggle_termination' in row:
                from crawl_jiggle_termination import recorded_detection
                full=z['pose'+suffix].astype(np.float64)
                angular_ids=[row['names'].index(b) for b in row['crawl_jiggle_termination'].get('angular_bodies',['right_hand','left_hand'])]
                flags,streak=recorded_detection(full,[row['names'].index(b) for b in ('right_hand','left_hand')],row['names'].index('pelvis'),row['fps'],angular_ids)
                if not row['crawl_jiggle_termination']['enabled']:flags[:]=False;streak[:]=0
                assert np.array_equal(flags,row['frame_crawl_jiggle_terminated'])
                assert np.array_equal(streak,row['frame_crawl_jiggle_streak'])
                hits=np.flatnonzero(flags)
                if len(hits):
                    assert hits[0]==len(full)-1, 'Rollout continued beyond jiggle failure'
                    assert data[-1,0]==1, 'Jiggle must be failure, not timeout'
            assert row['loco_failure_penalty'] in (100.,500.)
            checks.append(dict(label=row['replay_row_label'],motion=row['motion_name'],cohort=row['cohort_index'],
                terminal_flag=int(data[-1,0]),terminal_reward=float(data[-1,2]),mse_max_abs_errors=error))
    assert len(checks) in (8,33,34,40)
    return dict(passed=True,rows=checks)

if __name__=='__main__':
    result=verify(sys.argv[1])
    if len(sys.argv)>2:
        from pathlib import Path
        Path(sys.argv[2]).write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(passed=True,rows=len(result['rows']))))
