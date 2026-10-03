import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=Path(__file__).parent
tip=np.array([0.,0.,json.loads((p.parent/'PikeSword20261003/geometry.json').read_text())['max'][2]])
mirror=np.diag([1,-1,1])
def point(t,local):
    return np.array(t['p'])+R.from_quat(t['q']).apply(local*np.array(t['s']))
def groups(trace):
    gs=[]
    for r in trace:
        if not gs or r['frame']<=gs[-1][-1]['frame']:gs.append([])
        gs[-1].append(r)
    return gs
def native(row,tip_hand):
    out=np.array(row['output']);source=np.array(row['native_rotation']).reshape(3,3);carrier=R.from_quat(row['anchor'][3:]).as_matrix()
    pos=((out[131:206].reshape(25,3)-row['native_position'])@source.T@mirror*100)@carrier.T+row['anchor'][:3]
    rot=carrier@mirror@source@out[206:431].reshape(25,3,3).transpose(0,2,1)@mirror
    target=(np.array(row['input'][262:265])-row['native_position'])@source.T@mirror*100@carrier.T+row['anchor'][:3]
    return pos[13]+rot[13]@tip_hand,target
def metric(points,target):
    pts=np.array(points);direction=target-pts[0];direction/=np.linalg.norm(direction)
    delta=pts-pts[0];side=delta-(delta@direction)[:,None]*direction
    vel=np.diff(pts,axis=0);cross=vel-(vel@direction)[:,None]*direction
    return dict(lateral_max_cm=float(np.linalg.norm(side,axis=1).max()),lateral_travel_cm=float(np.linalg.norm(cross,axis=1).sum()),max_step_cm=float(np.linalg.norm(vel,axis=1).max()))
all_data={};report={};plot={}
for fn in p.glob('*-nn.jsonl'):
    name=fn.name.removesuffix('-nn.jsonl');data=json.loads((p/(name+'.json')).read_text())
    if data['reason']!='Complete':continue
    rows=data['rows'];bytick={r['tick']:r for r in rows};grip=data['metadata']['sword_grip'];tip_hand=point(grip,tip)
    tr=[r for r in map(json.loads,fn.read_text().splitlines()) if r['actor']=='BP_ProphecyManualPoseAgent_C_0'];gs=groups(tr)
    all_data[name]=dict(data=data,bytick=bytick,groups=gs)
    entries=[]
    for ordinal,g in enumerate(gs,1):
        outputs=np.array([z['output'] for z in g]);ar=np.where(outputs[:,431]>.5)[0];ht=np.where(outputs[:,432]>.5)[0]
        if not len(ar) or not len(ht):continue
        lo=int(ar[0]);hi=int(ht[0]);at=min(rows,key=lambda r:abs(r['time']-g[lo]['time']))['tick'];hit=min(rows,key=lambda r:abs(r['time']-g[hi]['time']))['tick']
        targets=[native(z,tip_hand)[1] for z in g];target=targets[lo]
        pts=[native(z,tip_hand)[0] for z in g[lo:hi+1]]
        active=[r for r in rows if r['attack_count']==ordinal and r['attack']]
        entry=dict(ordinal=ordinal,start=active[0]['tick'],end=active[-1]['tick'],armed=at,hit=hit,native=metric(pts,target))
        # AttackViewer publishes at alpha=0 and presents that endpoint two ticks later.
        displayed=[bytick[t] for t in range(at+2,hit+3) if t in bytick]
        for kind in ('future','presented','body'):
            sample=displayed if kind!='future' else [bytick[t] for t in range(at,hit+1)]
            pp=[point(r['bones']['hand_r'][kind],tip_hand) for r in sample]
            entry[kind]=metric(pp,target)
        blade=[point(r['sword_components']['sword'],tip) for r in displayed]
        entry['sword']=metric(blade,target)
        entry['drag_releases']={side:[r['tick'] for prev,r in zip(active,active[1:]) if prev['drag'][s] and not r['drag'][s]] for s,side in enumerate(('left','right'))}
        entry['foot_max_steps_cm']={side:float(max(np.linalg.norm(np.array(r['bones']['foot_'+side]['presented']['p'])-q['bones']['foot_'+side]['presented']['p']) for q,r in zip(active,active[1:]))) for side in ('l','r')}
        gp=[r for r in active if 'ghost' in r]
        entry['ghost_samples']=len(gp)
        if gp:
            entry['ghost_pelvis_matches_presented_cm']=float(max(np.linalg.norm(np.array(r['ghost']['pelvis']['p'])-r['bones']['pelvis']['presented']['p']) for r in gp))
            entry['ghost_draw_succeeded']=all(r['draw_ghost'] for r in gp)
            entry['ghost_real_foot_separation_cm']=float(max(np.linalg.norm(np.array(r['ghost']['foot_r']['p'])-r['bones']['foot_r']['presented']['p']) for r in gp))
        if ordinal==2:plot[name]=(displayed,np.array(blade),target)
        entries.append(entry)
    report[name]=dict(attacks=entries)

if 'control' in all_data:
    b=all_data['control'];brows=b['bytick'];start=report['control']['attacks'][1]['start']
    for name,d in all_data.items():
        if name=='control':continue
        report[name]['prefix_position_error_cm']=float(max(np.linalg.norm(np.array(r['bones'][bone]['presented']['p'])-brows[t]['bones'][bone]['presented']['p']) for t,r in d['bytick'].items() if t<=start for bone in r['bones']))
if 'ghost' in all_data and 'ghost_pelvis_off' in all_data:
    a=all_data['ghost'];b=all_data['ghost_pelvis_off'];active=[r for r in a['data']['rows'] if r['attack_count']==2 and r['attack']]
    report['pelvis_inertia_check']=dict(native_output_max_error=float(np.max(np.abs(np.array([r['output'] for r in a['groups'][1]])-np.array([r['output'] for r in b['groups'][1]])))),
        presented_max_position_effect_cm=float(max(np.linalg.norm(np.array(r['bones']['pelvis']['presented']['p'])-b['bytick'][r['tick']]['bones']['pelvis']['presented']['p']) for r in active)))
if 'ghost' in all_data and 'drag_off' in all_data:
    a=all_data['ghost']['groups'][1];b=all_data['drag_off']['groups'][1]
    report['ghost_vs_drag_off_native']=dict(frame_counts=[len(a),len(b)],max_error=float(np.max(np.abs(np.array([r['output'] for r in a[:min(len(a),len(b))]])-np.array([r['output'] for r in b[:min(len(a),len(b))]])))))
(p/'comparison.json').write_text(json.dumps(report,indent=2))
for name,r in report.items():
    if 'attacks' in r and len(r['attacks'])>1:
        e=r['attacks'][1];print(name,'second pike',e['armed'],e['hit'],'native',round(e['native']['lateral_max_cm'],3),'presented',round(e['presented']['lateral_max_cm'],3),'sword',round(e['sword']['lateral_max_cm'],3),'feet',e['foot_max_steps_cm'],'prefix',r.get('prefix_position_error_cm'))
    elif 'attacks' not in r:print(name,r)
if 'control' in plot:
    fig,axs=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True)
    for name in ('control','ghost','drag_off'):
        if name not in plot:continue
        rows,pts,target=plot[name];direction=target-pts[0];direction/=np.linalg.norm(direction)
        delta=pts-pts[0];along=delta@direction;side=np.linalg.norm(delta-along[:,None]*direction,axis=1)
        axs[0].plot(along,side,'.-',label=name);axs[1].plot([r['tick']-rows[0]['tick'] for r in rows],side,'.-',label=name)
    axs[0].set_xlabel('Forward blade travel from Armed (cm)');axs[1].set_xlabel('Game ticks after displayed Armed pose')
    for ax in axs:ax.set_ylabel('Distance across starting target ray (cm)');ax.grid(alpha=.3);ax.legend()
    fig.suptitle('Second pike: actual sword, Armed through Hit')
    fig.savefig(p/'blade-comparison.png',dpi=140)
