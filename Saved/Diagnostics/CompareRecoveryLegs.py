"""Compare captured recovery knees/feet as well as pelvis. Read-only, no Unreal use.
Usage: python CompareRecoveryLegs.py BASELINE CAPTURE [CAPTURE ...]
Windows/ticks default to first captured kickR recovery: 149-190; descent 149-169.
Output is CAPTURE/recovery_leg_comparison.json.
"""
import argparse,json,pathlib,numpy as np
from scipy.spatial.transform import Rotation
ROOT=pathlib.Path(__file__).resolve().parents[2]
OFF=np.array(json.loads((ROOT/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())['local_offsets_m'])
WALK=json.loads((ROOT/'Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json').read_text())
def unit(v):return v/max(1e-12,np.linalg.norm(v))
def rot(v):
    v=np.array(v);x=unit(v[:3]);y=unit(v[3:]-x*np.dot(x,v[3:]));return np.array([x,y,np.cross(x,y)])
def angle(a,b):return float(np.degrees(Rotation.from_matrix(a@b.T).magnitude()))
def direction_angle(a,b):return float(np.degrees(np.arccos(np.clip(np.dot(unit(a),unit(b)),-1,1))))
def load(path):
    path=pathlib.Path(path)
    if not path.exists():path=ROOT/'Saved/Diagnostics'/path
    summary=json.loads((path/'summary.json').read_text())
    actor=next(name for name,info in summary['info'].items() if info.get('player'))
    pipe={round(r['time']*60):r for r in map(json.loads,(path/'pipeline.jsonl').read_text().splitlines()) if r['actor']==actor}
    metrics={r['tick']:r for r in map(json.loads,(path/'metrics.jsonl').read_text().splitlines()) if r['agent']==actor}
    return path,pipe,metrics
def stats(v):
    v=np.array(v,dtype=float)
    return {'min':float(v.min()),'max':float(v.max()),'mean':float(v.mean()),'rms':float(np.sqrt(np.mean(v*v)))} if len(v) else None
def pose_metrics(pipe,start,end):
    out=[]
    for t,r in pipe.items():
        if not start<=t<=end or r.get('attack'):continue
        s=np.array(r['published_lower']);cur=np.array(r['lower_input'][:41]);raw=cur+np.array(r['lower_delta'][:41]);rec={'tick':t,'legs':{}}
        for i,side in enumerate(('left','right')):
            o=9+16*i;h=17+4*i;rr=rot(raw[o+9:o+15]);sr=rot(s[o+9:o+15]);cr=rot(cur[o+9:o+15]);upper=OFF[h+1]@sr;rawupper=OFF[h+1]@rr
            hip=s[:3]+OFF[h]@rot(s[3:9]);axis=unit(s[o:o+3]-hip);radial=upper-axis*np.dot(upper,axis)
            toe=unit(np.array(WALK['ik_toe_offsets_m'][i]))@rot(s[o+3:o+9]);forward=unit(toe*[1,1,0]);sideaxis=np.cross([0,0,1],forward);N=unit(sideaxis-axis*np.dot(sideaxis,axis));hpole=unit(np.cross(axis,N))
            rec['legs'][side]={'thigh_full_step_deg':angle(cr,sr),'thigh_direction_step_deg':direction_angle(OFF[h+1]@cr,upper),
               'raw_thigh_step_deg':angle(cr,rr),'raw_correction_deg':angle(rr,sr),'raw_knee_displacement_cm':float(np.linalg.norm(upper-rawupper)*100),
               'knee_forward_cm':float(np.dot(upper,forward)*100),'knee_side_cm':float(np.dot(upper,sideaxis)*100),
               'oriented_hinge_branch_score':float(np.dot(unit(radial),hpole)),
               'ankle_height_cm':float(s[o+2]*100),'foot_side_from_hip_cm':float(np.dot(s[o:o+3]-hip,sideaxis)*100),
               'hip_ankle_cm':float(np.linalg.norm(s[o:o+3]-hip)*100),'calf_length_error_cm':float((np.linalg.norm(s[o:o+3]-hip-upper)-np.linalg.norm(OFF[h+2]))*100)}
        out.append(rec)
    return out
def dynamic_metrics(m,start,end):
    ticks=[t for t in sorted(m) if start<=t<=end];out={}
    for bone in ('pelvis','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r'):
        ps=np.array([m[t]['bones'][bone]['target']['p'] for t in ticks]);qs=np.array([m[t]['bones'][bone]['target']['q'] for t in ticks]);v=np.diff(ps,axis=0);a=np.diff(v,axis=0)
        rotations=Rotation.from_quat(qs)
        angular=np.degrees((rotations[1:]*rotations[:-1].inv()).magnitude())
        out[bone]={'world_step_cm':stats(np.linalg.norm(v,axis=1)),'world_second_difference_cm':stats(np.linalg.norm(a,axis=1)),'world_rotation_step_deg':stats(angular)}
    for side in ('l','r'):
        dirs=[np.array(m[t]['bones']['calf_'+side]['target']['p'])-m[t]['bones']['thigh_'+side]['target']['p'] for t in ticks]
        out['thigh_'+side]['world_direction_step_deg']=stats([direction_angle(a,b) for a,b in zip(dirs[:-1],dirs[1:])])
    out['pelvis_backward_step_by_tick']={str(t):float(m[t-1]['bones']['pelvis']['target']['p'][1]-m[t]['bones']['pelvis']['target']['p'][1]) for t in ticks if t-1 in m}
    return out
def compare(base_path,path,start,end,descent_end):
    bp,b,mb=load(base_path);p,q,m=load(path)
    poses=pose_metrics(q,start,end);ranges={'recovery':(start,end),'early_descent':(start,descent_end),'hitch_window':(172,182)}
    result={'baseline':str(bp),'capture':str(p),'note':'Captured attack is kickR: LEFT initially supporting, RIGHT descending. Dynamic step/acceleration values use interpolated targets; baseline differences use future published targets. Physical bodies are not used. Full thigh orientation and knee-point direction are distinct.',
        'pose_rows':poses,'windows':{}}
    for name,(s,e) in ranges.items():
        common=[t for t in m if t in mb and s<=t<=e]
        diff={}
        for bone in ('pelvis','calf_l','foot_l','calf_r','foot_r'):
            dist=[float(np.linalg.norm(np.array(m[t]['bones'][bone]['future']['p'])-mb[t]['bones'][bone]['future']['p'])) for t in common]
            diff[bone+'_world_vs_baseline_cm']=stats(dist)
        joint={}
        for side in ('left','right'):
            rs=[r['legs'][side] for r in poses if s<=r['tick']<=e]
            joint[side]={k:stats([r[k] for r in rs]) for k in rs[0]} if rs else {}
        result['windows'][name]={'dynamic':dynamic_metrics(m,s,e),'baseline_dynamic':dynamic_metrics(mb,s,e),'difference':diff,'pose':joint}
    outfile=p/'recovery_leg_comparison.json';outfile.write_text(json.dumps(result,indent=2))
    summary={'capture':p.name,'output':str(outfile)}
    for name,window in result['windows'].items():
        summary[name]={'pelvis_accel_cm':window['dynamic']['pelvis']['world_second_difference_cm'],
            'pelvis_accel_baseline_cm':window['baseline_dynamic']['pelvis']['world_second_difference_cm'],
            'left_thigh_world_direction_step':window['dynamic']['thigh_l']['world_direction_step_deg'],
            'right_foot_accel_cm':window['dynamic']['foot_r']['world_second_difference_cm'],
            'right_knee_max_world_difference_cm':window['difference']['calf_r_world_vs_baseline_cm'],
            'right_foot_max_world_difference_cm':window['difference']['foot_r_world_vs_baseline_cm']}
    print(json.dumps(summary,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('baseline');ap.add_argument('captures',nargs='+');ap.add_argument('--start',type=int,default=149);ap.add_argument('--end',type=int,default=190);ap.add_argument('--descent-end',type=int,default=169);args=ap.parse_args()
    for path in args.captures:compare(args.baseline,path,args.start,args.end,args.descent_end)
