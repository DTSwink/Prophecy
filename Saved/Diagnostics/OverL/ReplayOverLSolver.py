"""Offline stage replay of retained tempering solver; never touches Unreal.

Uses captured final endpoints to isolate rotation correction. Replay error is
reported, not hidden; pelvis inertia / changing kick extension invalidate this
fixed-reference-calf replay when active.
"""
import argparse,json,pathlib,numpy as np
from scipy.spatial.transform import Rotation,Slerp
ROOT=pathlib.Path(__file__).resolve().parents[3]
RUN=json.loads((ROOT/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())
WALK=json.loads((ROOT/'Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json').read_text())
OFF=np.array(RUN['local_offsets_m'])
def unit(v):return v/max(1e-12,np.linalg.norm(v))
def project(v,a):return unit(v-a*np.dot(v,a))
def rot(v):
    v=np.asarray(v);x=unit(v[:3]);y=project(v[3:],x);return np.array([x,y,np.cross(x,y)])
def angle(x,y):return float(np.degrees(Rotation.from_matrix(x@y.T).magnitude()))
def smooth(x):x=np.clip(x,0,1);return x*x*(3-2*x)
def slerp(a,b,w):return Slerp([0,1],Rotation.from_matrix([a,b]))([w]).as_matrix()[0]
def axis_angle(a,v):return Rotation.from_rotvec(a*v).as_matrix().T
def clean(s):
    s=s.copy()
    for o in (3,12,18,28,34):s[o:o+6]=rot(s[o:o+6])[:2].reshape(-1)
    s[[24,40]]=np.clip(s[[24,40]],-1,1)
    return s
def policy_source(r,i):
    raw=clean(np.array(r['lower_input'][:41])+r['lower_delta'][:41])
    w=r.get(('left_walk_weight','right_walk_weight')[i],r['walk_weight'])
    if 'walk_delta' not in r:return raw,WALK if w==1 else RUN
    walk=clean(np.array(r['lower_input'][:41])+r['walk_delta'][:41]);o=9+16*i
    for pos in (0,o):raw[pos:pos+3]=raw[pos:pos+3]*(1-w)+walk[pos:pos+3]*w
    for pos in (3,o+3,o+9):raw[pos:pos+6]=slerp(rot(raw[pos:pos+6]),rot(walk[pos:pos+6]),w)[:2].reshape(-1)
    raw[o+15]=(1-w)*raw[o+15]+w*walk[o+15]
    assert w in (0,1),'Mixed runtime limb geometry not implemented'
    return raw,WALK if w==1 else RUN
def sole_min(p,r,toe,i,policy):
    toeoff=np.array(policy['ik_toe_offsets_m'][i]);tp=p+toeoff@r;tv=tp-p
    up,fw,side=r.copy();fw*=(-1 if fw@tv<0 else 1);up*=(-1 if up[2]<0 else 1)
    fr=RUN['foot_roll'];fh=np.array(fr['foot_half_dims_m']);th=np.array(fr['toe_half_dims_m']);so=fr['sole_vertical_offset_m']
    fc=tp-fw*fh[0]+up*so
    tr=axis_angle(np.array(policy['ik_toe_axes'][i]),np.clip(toe,-1,1)*policy['ik_toe_alpha_rad'])@r
    tf,tu,ts=tr;tf=tf*(-1 if tf@tv<0 else 1);tu=tu*(-1 if tu[2]<0 else 1)
    tc=tp+tf*th[0]+tu*so
    return min(fc[2]-np.abs([fw[2],side[2],up[2]])@fh,tc[2]-np.abs([tf[2],ts[2],tu[2]])@th)
def solve_record(r,i):
    s=np.array(r['published_lower']);prev=np.array(r['previous_lower']);raw,policy=policy_source(r,i)
    o=9+16*i;hidx=17+4*i;L1=np.linalg.norm(OFF[hidx+1]);L2=np.linalg.norm(OFF[hidx+2]);limit=L1+L2-2e-5
    sole=sole_min(s[o:o+3],rot(s[o+3:o+9]),s[o+15],i,policy)-1e-5
    difference=angle(rot(prev[o+9:o+15]),rot(raw[o+9:o+15]));support=1-smooth((sole-.02)/.10)
    follow=support*min(1,20/max(difference,1e-6)) if r['tempering'][1]>0 else 0
    src=prev.copy()
    for pos in (0,o):src[pos:pos+3]=(1-follow)*prev[pos:pos+3]+follow*raw[pos:pos+3]
    for pos in (3,o+9):src[pos:pos+6]=slerp(rot(prev[pos:pos+6]),rot(raw[pos:pos+6]),follow)[:2].reshape(-1)
    oldr=rot(src[o+9:o+15]);oldhip=src[:3]+OFF[hidx]@rot(src[3:9]);oldupper=OFF[hidx+1]@oldr
    oldaxis=unit(src[o:o+3]-oldhip);oldbend=oldupper-oldaxis*(oldupper@oldaxis);oldpole=unit(oldbend)
    hip=s[:3]+OFF[hidx]@rot(s[3:9]);end=s[o:o+3];axis=unit(end-hip)
    cosine=np.clip(oldaxis@axis,-1,1)
    carried=project(-oldpole if cosine<(-1+1e-6) else oldpole-(oldaxis+axis)*(oldpole@axis)/max(1e-6,1+cosine),axis)
    d=min(np.linalg.norm(end-hip),limit);along=(L1*L1-L2*L2+d*d)/(2*d);radius=np.sqrt(max(0,L1*L1-along*along))
    upper=axis*along+carried*radius;oldn=unit(np.cross(oldaxis,oldpole));newn=unit(np.cross(axis,carried))
    oldbasis=np.array([unit(oldupper),unit(np.cross(oldn,unit(oldupper))),oldn]);newbasis=np.array([unit(upper),unit(np.cross(newn,unit(upper))),newn])
    transported=oldr@oldbasis.T@newbasis
    footrot=rot(s[o+3:o+9]);toe=unit(np.array(policy['ik_toe_offsets_m'][i]))@footrot;flat=toe*[1,1,0]
    forward=unit(flat);sideaxis=np.cross([0,0,1],forward)
    radial=upper-axis*(upper@axis);R=np.linalg.norm(radial);pole=unit(radial);sidealong=axis@sideaxis;N0=sideaxis-axis*sidealong;Nlen=np.linalg.norm(N0);N=unit(N0)
    Q=-along*sidealong/max(1e-12,R*Nlen);strength=smooth(flat@flat*4)*smooth(Nlen*Nlen*4)*smooth((1-abs(Q))*4)
    desired=N*np.clip(Q,-1,1)+unit(np.cross(axis,N))*np.sqrt(max(0,1-np.clip(Q,-1,1)**2))
    fullturn=np.arctan2(axis@np.cross(pole,desired),np.clip(pole@desired,-1,1));turn=fullturn*strength if r['tempering'][1]>0 else 0
    final=transported@axis_angle(axis,turn);actual=rot(s[o+9:o+15]);prevrot=rot(prev[o+9:o+15]);rawrot=rot(raw[o+9:o+15])
    pk=prev[:3]+OFF[hidx]@rot(prev[3:9])+OFF[hidx+1]@prevrot;sk=hip+OFF[hidx+1]@transported;fk=hip+OFF[hidx+1]@final
    values={'source_follow':follow,'source_difference_deg':difference,'sole_clearance_cm':sole*100,'source_bend_radius_cm':np.linalg.norm(oldbend)*100,
            'transport_step_deg':angle(prevrot,transported),'guidance_turn_deg':np.degrees(turn),'guidance_full_turn_deg':np.degrees(fullturn),
            'previous_to_raw_deg':angle(prevrot,rawrot),'raw_to_transport_deg':angle(rawrot,transported),'raw_to_final_deg':angle(rawrot,actual),
            'published_step_deg':angle(prevrot,actual),'replay_error_deg':angle(final,actual),'Q':Q,'strength':strength,'hip_ankle_cm':d*100,
            'transport_knee_delta_cm':(sk-pk)*100,'guidance_knee_delta_cm':(fk-sk)*100,'knee_previous_cm':pk*100,'knee_transport_cm':sk*100,
            'knee_final_cm':fk*100,'axis':axis,'knee_radius_cm':R*100,'source_rotation':oldr,'transported_rotation':transported,'final_rotation':final}
    return {k:v.tolist() if isinstance(v,np.ndarray) else float(v) for k,v in values.items()}
def main():
    p=argparse.ArgumentParser();p.add_argument('capture');p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int,default=100000);p.add_argument('--output',default='stage-replay.json');args=p.parse_args()
    source=pathlib.Path(args.capture);source=source if source.is_absolute() else ROOT/source
    rows=[json.loads(x) for x in (source/'pipeline.jsonl').read_text().splitlines()];out=[]
    for r in rows:
        tick=round(r['time']*60)
        if not r['actor'].endswith('_C_1') or r['attack'] or 'tempering' not in r or not args.start<=tick<=args.end:continue
        record={'tick':tick,'tempering':r['tempering'],'legs':{side:solve_record(r,i) for i,side in enumerate(('left','right'))}}
        print(tick,{side:{k:round(v,3) for k,v in leg.items() if k in ('source_follow','transport_step_deg','guidance_turn_deg','published_step_deg','replay_error_deg','Q','strength')} for side,leg in record['legs'].items()})
        out.append(record)
    (pathlib.Path(__file__).parent/args.output).write_text(json.dumps(out,indent=2))
if __name__=='__main__':main()
