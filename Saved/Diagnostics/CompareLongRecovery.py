"""Paired independent quality review; detects actual tempering windows."""
import argparse,pathlib,json,runpy,numpy as np
F=pathlib.Path(__file__).parent
H=runpy.run_path(str(F/'CompareRecoveryLegs.py'))
def capture(name):
    path,p,m=H['load'](name);poses={r['tick']:r for r in H['pose_metrics'](p,1,max(m))};runs=[]
    for tick,r in p.items():
        if r.get('tempering') and not r.get('attack'):
            if not runs or tick>runs[-1][-1]+3:runs.append([])
            runs[-1].append(tick)
    return path,p,m,poses,runs
def summarize(data):
    path,p,m,poses,runs=data;out=[]
    for cycle,run in enumerate(runs):
        start,last=run[0],run[-1];dyn=H['dynamic_metrics'](m,start,last+12);retire=H['dynamic_metrics'](m,last,last+4);hitch=H['dynamic_metrics'](m,start+23,start+33)
        row={'cycle':cycle+1,'start':start,'last_tempered':last,'pelvis_hitch_accel_max':hitch['pelvis']['world_second_difference_cm']['max'],'legs':{}}
        for side,letter in [('left','l'),('right','r')]:
            ps=[poses[t]['legs'][side] for t in run];floorreach=next((t for t in run if poses[t]['legs'][side]['ankle_height_cm']<=20),None)
            until=run if floorreach is None else [t for t in run if t<=floorreach]
            heights=[poses[t]['legs'][side]['ankle_height_cm'] for t in until]
            row['legs'][side]={'max_knee_side_cm':max(abs(r['knee_side_cm']) for r in ps),'min_branch_score':min(r['oriented_hinge_branch_score'] for r in ps),
                'max_thigh_direction_step_deg':max(r['thigh_direction_step_deg'] for r in ps),'max_full_thigh_step_deg':max(r['thigh_full_step_deg'] for r in ps),
                'world_knee_accel_max':dyn['calf_'+letter]['world_second_difference_cm']['max'],'world_foot_accel_max':dyn['foot_'+letter]['world_second_difference_cm']['max'],
                'world_thigh_rotation_step_max':dyn['thigh_'+letter]['world_rotation_step_deg']['max'],'world_calf_rotation_step_max':dyn['calf_'+letter]['world_rotation_step_deg']['max'],
                'retirement_thigh_rotation_step_max':retire['thigh_'+letter]['world_rotation_step_deg']['max'],'retirement_calf_rotation_step_max':retire['calf_'+letter]['world_rotation_step_deg']['max'],
                'retirement_knee_accel_max':retire['calf_'+letter]['world_second_difference_cm']['max'],
                'first_height_below_20cm':floorreach,'descent_upward_steps_above_20cm':int(sum(b>a+.01 for a,b in zip(heights[:-1],heights[1:])))}
        out.append(row)
    return out
def compare(base,cand):
    b=capture(base);c=capture(cand);bs=summarize(b);cs=summarize(c);pairs=[]
    for rb,rc,br,cr in zip(bs,cs,b[-1],c[-1]):
        diffs={}
        for side in ('left','right'):
            bp=[b[3][t]['legs'][side] for t in br];cp=[c[3][t]['legs'][side] for t in cr]
            for key in ('ankle_height_cm','foot_side_from_hip_cm','knee_forward_cm'):
                diffs[side+'_'+key+'_max_delta']=max(abs(x[key]-y[key]) for x,y in zip(bp,cp))
            early=[(x,y) for x,y in zip(bp,cp) if min(x['ankle_height_cm'],y['ankle_height_cm'])>20]
            diffs[side+'_early_ankle_height_max_delta']=max((abs(x['ankle_height_cm']-y['ankle_height_cm']) for x,y in early),default=0)
            o=9 if side=='left' else 25
            early_vectors=[]
            for bt,ct in zip(br,cr):
                if min(b[3][bt]['legs'][side]['ankle_height_cm'],c[3][ct]['legs'][side]['ankle_height_cm'])<=20:continue
                bs=np.array(b[1][bt]['published_lower']);cs=np.array(c[1][ct]['published_lower'])
                early_vectors.append(((bs[o:o+3]-bs[:3])-(cs[o:o+3]-cs[:3]))*100)
            diffs[side+'_early_foot_relative_pelvis_xyz_max_delta_cm']=np.max(abs(np.array(early_vectors)),axis=0).tolist() if early_vectors else [0,0,0]
        pair={'cycle':rb['cycle'],'baseline':rb,'candidate':rc,'relative_curve_differences':diffs};pairs.append(pair)
        print(json.dumps({'cycle':rb['cycle'],'hitch_accel':[rb['pelvis_hitch_accel_max'],rc['pelvis_hitch_accel_max']],
            'left_maxside':[rb['legs']['left']['max_knee_side_cm'],rc['legs']['left']['max_knee_side_cm']],
            'right_maxside':[rb['legs']['right']['max_knee_side_cm'],rc['legs']['right']['max_knee_side_cm']],
            'right_branch':[rb['legs']['right']['min_branch_score'],rc['legs']['right']['min_branch_score']],
            'left_maxthigh':[rb['legs']['left']['world_thigh_rotation_step_max'],rc['legs']['left']['world_thigh_rotation_step_max']],
            'right_maxthigh':[rb['legs']['right']['world_thigh_rotation_step_max'],rc['legs']['right']['world_thigh_rotation_step_max']],
            'right_retirethigh':[rb['legs']['right']['retirement_thigh_rotation_step_max'],rc['legs']['right']['retirement_thigh_rotation_step_max']],
            'descent_height_difference':diffs['right_early_ankle_height_max_delta'],'descent_upsteps':rc['legs']['right']['descent_upward_steps_above_20cm']}))
    result={'baseline':str(b[0]),'candidate':str(c[0]),'pairs':pairs}
    (c[0]/'long_recovery_independent_review.json').write_text(json.dumps(result,indent=2))
    return result
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('baseline');ap.add_argument('candidate');a=ap.parse_args();compare(a.baseline,a.candidate)
