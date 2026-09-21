import pathlib,json,sys,math,numpy as np
from ReplayTemperedLeg import unit,points,rot,config,offsets,clean,mixstate
p=pathlib.Path(sys.argv[1]);out=[]
for line in (p/'pipeline.jsonl').open():
    r=json.loads(line)
    if r['actor']!='BP_ProphecyManualPoseAgent_C_1' or r['attack'] or r['time']<1:continue
    raw=clean(np.array(r['lower_input'][:41])+np.array(r['lower_delta'][:41]))
    if 'walk_delta' in r:raw=mixstate(raw,clean(np.array(r['lower_input'][:41])+np.array(r['walk_delta'][:41])),r['walk_weight'])
    s=np.array(r['published_lower']);h,k,a,t=points(s);A=unit(a-h)
    u=offsets[18]@rot(raw,18);fw=unit((t-a)*[1,1,0]);side=np.cross([0,0,1],fw);T=unit(np.cross(A,side))
    oldfw=unit(np.array(config['ik_toe_offsets_m'][0])@rot(raw,12)*[1,1,0])
    angle=math.atan2(np.cross(oldfw,fw)[2],np.dot(oldfw,fw));c=math.cos(angle);sn=math.sin(angle)
    aligned=np.array([c*u[0]-sn*u[1],sn*u[0]+c*u[1],u[2]])
    out.append(dict(t=r['time'],z=A[2],raw_sign=float(np.dot(unit(u-A*np.dot(u,A)),T)),aligned_sign=float(np.dot(unit(aligned-A*np.dot(aligned,A)),T)),yaw_delta=math.degrees(angle)))
print('negative below',sum(x['raw_sign']<0 and x['z']<0 for x in out),sum(x['aligned_sign']<0 and x['z']<0 for x in out),'/',len(out))
print(json.dumps([x for x in out if x['z']<0 and (x['raw_sign']<0 or x['aligned_sign']<0)][:20]))
