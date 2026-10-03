import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
d=json.loads(Path(sys.argv[1]).read_text());contract=json.loads(Path('Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text());mirror=np.array([1,-1,1]);names=contract['body_names']
unit=lambda v:v/max(np.linalg.norm(v),1e-12)
def oracle(row,side,slot=0):
    i=0 if side=='l' else 1;b=row['bones'];t=b['thigh_'+side][slot];c=b['calf_'+side][slot];f=b['foot_'+side][slot]
    main=unit(np.array(contract['local_offsets_m'][names.index('foot_'+side)])*mirror)
    thigh=unit(np.array(contract['local_offsets_m'][names.index('calf_'+side)])*mirror)
    poles=np.array(contract['ik_local_pole_axes'][i])*mirror
    lh=unit(np.cross(main,poles[1]));wh=R.from_quat(t[3:]).apply(unit(np.cross(thigh,poles[0])))
    wm=unit(np.array(f[:3])-c[:3]);ws=unit(np.cross(wh,wm));wn=unit(np.cross(wm,ws));ws=unit(np.cross(wn,wm))
    ls=unit(np.cross(lh,main));ln=unit(np.cross(main,ls))
    return R.from_matrix(np.stack([wm,ws,wn],axis=1)@np.stack([main,ls,ln])),main
stats={};last={};events=[]
for row in d['rows']:
    a=row['agent'];prev=last.get(a);last[a]=row
    for side in ['l','r']:
        b=row['bones'];calf='calf_'+side;thigh='thigh_'+side
        expected,axis=oracle(row,side);q=R.from_quat(b[calf][0][3:]);difference=np.rad2deg((expected.inv()*q).magnitude())
        key=f"{a}:{row['state']}:{side}";s=stats.setdefault(key,{'samples':0,'mismatch':[],'calf_step':[],'thigh_step':[],'swing_step':[],'twist_step':[],'oracle_step':[],'physical_step':[]})
        s['samples']+=1;s['mismatch'].append(difference)
        if prev and prev['state']==row['state']:
            pq=R.from_quat(prev['bones'][calf][0][3:]);pt=R.from_quat(prev['bones'][thigh][0][3:]);t=R.from_quat(b[thigh][0][3:]);peq,_=oracle(prev,side)
            delta=pq.inv()*q;dq=delta.as_quat();twist=abs(np.rad2deg(2*np.arctan2(np.dot(dq[:3],axis),dq[3])));twist=min(twist,360-twist)
            values={'calf_step':np.rad2deg(delta.magnitude()),'thigh_step':np.rad2deg((pt.inv()*t).magnitude()),'swing_step':np.rad2deg(np.arccos(np.clip(pq.apply(axis)@q.apply(axis),-1,1))),'twist_step':twist,'oracle_step':np.rad2deg((peq.inv()*expected).magnitude())}
            if row.get('physical') and prev.get('physical'):values['physical_step']=np.rad2deg((R.from_quat(prev['physical'][calf][3:]).inv()*R.from_quat(row['physical'][calf][3:])).magnitude())
            for k,v in values.items():s[k].append(float(v))
            if values['twist_step']>15:events.append({'agent':a,'frame':row['frame'],'side':side,'attack':row['attack'],'mismatch':float(difference),**{k:float(v) for k,v in values.items()}})
for s in stats.values():
    for k,v in list(s.items()):
        if isinstance(v,list):s[k]={'max':max(v) if v else 0,'p95':float(np.percentile(v,95)) if v else 0}
out={'error':d['error'],'frames':d['frames'],'stats':stats,'events':sorted(events,key=lambda e:e['twist_step'],reverse=True)[:30]}
Path(sys.argv[1]).with_suffix('.metrics.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
