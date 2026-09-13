"""Measure source foot/toe contact geometry, raw-to-publication parity and player camera tracking."""
import json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[2]
DIR=ROOT/'Saved/Diagnostics/SlashContacts'
G=json.loads((ROOT/'Content/locomotion/NN/prophecy_slash_native.json').read_text())
R=np.array(G['root_rotation']); P=np.array(G['root_position']); M=np.diag([1,-1,1])
NAMES=G['bone_names']

def box(center,f,s,u,half):
    sign=lambda z: -1 if z>1e-5 else (1 if z< -1e-5 else 0)
    lateral=np.clip(np.arcsin(np.clip(abs(s[2]),0,1))/np.deg2rad(8),0,1)
    return center+f*sign(f[2])*half[0]+s*sign(s[2])*half[1]*lateral-u*half[2]

def contact(bones,side):
    foot=bones['foot_'+side];toe=bones['ball_'+side]
    fp=np.array(foot['p']);tp=np.array(toe['p']);v=tp-fp
    fr=Rotation.from_quat(foot['q']).as_matrix().T
    tr=Rotation.from_quat(toe['q']).as_matrix().T
    u,f,s=fr[0],fr[1],fr[2]
    tf,tu,ts=tr[0],tr[1],tr[2]
    if np.dot(f,v)<0:f=-f
    if u[2]<0:u=-u
    if np.dot(tf,v)<0:tf=-tf
    if tu[2]<0:tu=-tu
    fh=np.array(G['foot_half_dims'])*100;th=np.array(G['toe_half_dims'])*100
    fc=tp-f*fh[0]+u*G['sole_offset']*100
    tc=tp+tf*th[0]+tu*G['sole_offset']*100
    return min(box(fc,f,s,u,fh)[2],box(tc,tf,ts,tu,th)[2])

def raw_bones(step):
    out=np.array(step['output']);a=step['anchor'];ar=Rotation.from_quat(a[3:]).as_matrix().T
    pos=(out[131:206].reshape(25,3)-P)@R.T@M*100@ar+np.array(a[:3])
    rot=M@out[206:431].reshape(25,3,3)@R.T@M@ar
    q=Rotation.from_matrix(rot.transpose(0,2,1)).as_quat()
    return {n:{'p':p.tolist(),'q':r.tolist()} for n,p,r in zip(NAMES,pos,q)}

def stats(x):
    a=np.array(x)
    return {'count':len(a),'min':float(a.min()),'p50':float(np.median(a)),'p95':float(np.quantile(a,.95)),'max':float(a.max())} if len(a) else {}

def main(label,trace):
    survey=json.loads((DIR/(label+'.json')).read_text())
    steps=[json.loads(x) for x in (DIR/trace).read_text().splitlines()]
    times=np.array([s['time'] for s in steps]);actor=steps[0]['actor']
    raw=[raw_bones(s) for s in steps]
    report={'survey_reason':survey['reason'],'raw_contact_cm_above_floor':{},'pins':{},'actors':{}}
    for side,i in [('l',435),('r',436)]:
        report['raw_contact_cm_above_floor'][side]=stats([contact(b,side)+.5 for b in raw])
        pins=np.array([s['output'][i] for s in steps])
        report['pins'][side]={'range':[float(pins.min()),float(pins.max())],'positive_fraction':float((pins>0).mean()),'mean':float(pins.mean())}
    for name in sorted(set(r['actor'] for r in survey['rows'])):
        phases={}
        for phase in [0,1]:
            rows=[r for r in survey['rows'] if r['actor']==name and r['phase']==phase and r['t']>2]
            entry={'samples':len(rows),'modes':sorted(set(r['mode'] for r in rows))}
            for side in ['l','r']:
                entry['mesh_contact_'+side]=stats([contact({b:v['mesh'] for b,v in r['bones'].items()},side)+.5 for r in rows])
                entry['mesh_target_error_'+side]=stats([np.linalg.norm(np.array(r['bones']['foot_'+side]['mesh']['p'])-r['bones']['foot_'+side]['shown']['p']) for r in rows])
            rel=[np.array(r['bones']['pelvis']['mesh']['p'])[:2]-(np.array(r['spring'])+r['target_offset'])[:2] for r in rows]
            entry['camera_pelvis_relative_spread_cm']=(np.ptp(rel,axis=0).tolist() if len(rel) else [])
            if name==actor:
                errors=[]
                for row in rows:
                    idx=int(np.searchsorted(times,row['t']+1e-5,side='right')-1)
                    if idx<0 or abs(times[idx]-row['t'])>.04 or steps[idx]['frame']!=row['frame']:continue
                    for b in ['foot_l','foot_r']:
                        errors.append(np.linalg.norm(np.array(row['bones'][b]['future']['p'])-raw[idx][b]['p']))
                entry['raw_to_future_foot_cm']=stats(errors)
            phases[str(phase)]=entry
        report['actors'][name]=phases
    (DIR/(label+'_analysis.json')).write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main(sys.argv[1],sys.argv[2])
