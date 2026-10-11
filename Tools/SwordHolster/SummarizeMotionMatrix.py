"""Numerical motion/phase audit; retains worst tick and bone for each channel."""
import json, math, pathlib, sys, statistics
from SummarizeHeadFps import angle
root=pathlib.Path(__file__).resolve().parents[2];folder=root/(sys.argv[1] if len(sys.argv)>1 else 'Saved/Diagnostics/SwordOvernight20261011/initial')
def qm(a,b):
    x,y,z,w=a;X,Y,Z,W=b
    return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def inv(q): return [-q[0],-q[1],-q[2],q[3]]
parents={'spine_01':'pelvis','spine_02':'spine_01','spine_03':'spine_02','spine_04':'spine_03','spine_05':'spine_04','neck_01':'spine_05','neck_02':'neck_01','head':'neck_02','clavicle_r':'spine_05','upperarm_r':'clavicle_r','lowerarm_r':'upperarm_r','hand_r':'lowerarm_r'}
def local(p,b):return qm(inv(p[parents[b]][-4:]),p[b][-4:])
results=[]
for file in sorted(folder.glob('*.json')):
    if not file.stem.startswith(('sim-','kinematic-')): continue
    data=json.loads(file.read_text());rows=data['rows'];result=dict(name=file.stem,reason=data['reason'],actors={})
    if not rows: results.append(result);continue
    result['missing_ticks']=sum(max(0,b['tick']-a['tick']-1) for a,b in zip(rows,rows[1:]))
    result['dt_range']=[min(r['dt'] for r in rows),max(r['dt'] for r in rows)]
    result['fps']=(rows[-1]['tick']-rows[0]['tick'])/(rows[-1]['wall']-rows[0]['wall'])
    for name in rows[0]['actors']:
        events=[];old=None;peaks={};lengths={};nonfinite=0;last_active=-100
        def peak(key,val,tick,bone=''):
            if key not in peaks or val>peaks[key][0]:peaks[key]=[val,tick,bone]
        for i,row in enumerate(rows):
            n=row['tick'];v=row['actors'][name];phase=v['fields'].get('phase');active=phase in (0,1,2,4)
            if active:last_active=n
            if phase!=old:events.append([n,phase]);old=phase
            for ch in ('future','target','physical'):
                for b,p in v[ch].items():nonfinite+=sum(not math.isfinite(x) for x in p)
            if i==0:continue
            previous=rows[i-1];pv=previous['actors'][name];dt=n-previous['tick']
            peak('root_speed_cm_s',math.dist(v['root'][:3],pv['root'][:3])*60/dt,n)
            if n>last_active+15: continue
            peak('hand_tracking_cm',math.dist(v['target']['hand_r'][:3],v['physical']['hand_r'][:3]),n)
            if phase==2:peak('sliding_grip_cm',v['fields'].get('pose_error',0),n)
            for ch in ('future','target','physical'):
                for b in v[ch]:
                    if b not in pv[ch]:continue
                    family='neck' if b in ('neck_01','neck_02','head') else 'arm' if b in ('clavicle_r','upperarm_r','lowerarm_r','hand_r') else 'body'
                    peak(ch+'_'+family+'_world_step_deg',angle(v[ch][b],pv[ch][b])/dt,n,b)
                    if b in parents and parents[b] in v[ch]:
                        peak(ch+'_'+family+'_local_step_deg',angle(local(v[ch],b),local(pv[ch],b))/dt,n,b)
                if ch!='future':peak(ch+'_head_step_deg',angle(v[ch]['head'],pv[ch]['head'])/dt,n,'head')
            for b in ('neck_01','neck_02','head'):
                peak('neck_tracking_deg',angle(v['target'][b],v['physical'][b]),n,b)
        result['actors'][name]=dict(player=name==data['player'],events=events,peaks=peaks,nonfinite=nonfinite,action=data.get('actions',{}).get(name))
    results.append(result)
(folder/'analysis.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
for r in results:
    print(r['name'],r['reason'],'missing',r.get('missing_ticks'))
    for name,v in r['actors'].items():
        p=v['peaks'];print(name,v['events'],'speed',p.get('root_speed_cm_s'),'neck target/phys',p.get('target_neck_local_step_deg'),p.get('physical_neck_local_step_deg'),'arm',p.get('target_arm_local_step_deg'),'tracking',p.get('hand_tracking_cm'))
