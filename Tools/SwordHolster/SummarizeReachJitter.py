"""Summarize numerical reach continuity captures; does not control the editor."""
import argparse
import json
import math
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[2]/'Saved/Diagnostics/SwordReachJitter20261011')
args = parser.parse_args()

def multiply(a, b):
    x,y,z,w=a; X,Y,Z,W=b
    return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]

def inverse(q):
    return [-q[0],-q[1],-q[2],q[3]]

def angle(a, b):
    dot=abs(sum(x*y for x,y in zip(a,b)))/math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return math.degrees(2*math.acos(min(1,dot)))

def local(actor, bone, parent):
    return multiply(inverse(actor['target'][parent][3:]),actor['target'][bone][3:])

def summarize(data):
    rows=data['rows']
    result=dict(reason=data['reason'],rows=len(rows),cap=data['options']['fps'],actual_fps=(rows[-1]['tick']-rows[0]['tick'])/(rows[-1]['wall']-rows[0]['wall']),world_deltas=sorted(set(r['dt'] for r in rows)),draw_results=data.get('draw_results'),actors={})
    for name in rows[0]['actors']:
        actor=dict(events=[],reach=[],finite=True,return_head_step=0,return_neck_step=0)
        previous=None; last=None
        for row in rows:
            current=row['actors'][name]; fields=current['fields']; phase=fields['phase']
            if phase!=last:
                actor['events'].append([row['tick'],phase]);last=phase
            actor['finite'] &= all(math.isfinite(v) for source in ['target','future','physical'] for pose in current[source].values() for v in pose)
            if previous and phase==1:
                step=dict(tick=row['tick'],pose_tick=fields['pose_tick'],progress=fields['progress'],hand_cm=math.dist(current['target']['hand_r'][:3],previous['target']['hand_r'][:3]),tracking_cm=math.dist(current['target']['hand_r'][:3],current['physical']['hand_r'][:3]))
                for bone,parent in [('upperarm_r','clavicle_r'),('lowerarm_r','upperarm_r'),('hand_r','lowerarm_r')]:
                    step[bone]=angle(local(current,bone,parent),local(previous,bone,parent))
                actor['reach'].append(step)
            if previous and phase==4:
                actor['return_head_step']=max(actor['return_head_step'],angle(current['target']['head'][3:],previous['target']['head'][3:]))
                actor['return_neck_step']=max(actor['return_neck_step'],*(angle(current['target'][bone][3:],previous['target'][bone][3:]) for bone in ['neck_01','neck_02']))
            previous=current
        result['actors'][name]=actor
    return result

data={p.stem:json.loads(p.read_text()) for p in sorted(args.directory.glob('*.json')) if p.stem.startswith(('before-','after-'))}
summary={name:summarize(d) for name,d in data.items()}
after=[name for name in data if name.startswith('after-')]
checks={}
if after:
    reference=data[after[0]]['rows']
    checks['all_replays_completed']=all(s['reason']=='captured' and s['rows']==323 and all(a['finite'] and a['events'][-1][1]==-1 and sum(e[1]==4 for e in a['events'])==2 for a in s['actors'].values()) for n,s in summary.items() if n in after)
    checks['all_draw_requests_accepted']=all(all(ok for _,ok in data[n]['draw_results']) for n in after)
    checks['all_pose_samples_identical']=all(len(data[n]['rows'])==len(reference) and all(a['tick']==b['tick'] and all(a['actors'][actor][source]==b['actors'][actor][source] for actor in a['actors'] for source in ['target','future','physical']) for a,b in zip(reference,data[n]['rows'])) for n in after)
    checks['all_event_ticks_identical']=all([a['events'] for a in summary[n]['actors'].values()]==[a['events'] for a in summary[after[0]]['actors'].values()] for n in after)
    checks['baseline_event_ticks_preserved']=all(a['events']==[e for e in summary[after[0]]['actors'][actor]['events'] if e[0]<=data[n]['rows'][-1]['tick']] for n,s in summary.items() if n.startswith('before-') for actor,a in s['actors'].items())
    checks['selected_player_steps']={n:{str(t):next((s for s in summary[n]['actors'][d['player']]['reach'] if s['tick']==t),None) for t in [61,65,205]} for n,d in data.items()}
(args.directory/'motion-summary.json').write_text(json.dumps(summary,indent=2))
(args.directory/'matrix-checks.json').write_text(json.dumps(checks,indent=2))
for n,s in summary.items():
    print(n,s['reason'],s['rows'],'FPS',round(s['actual_fps'],2))
    for actor,a in s['actors'].items():print(' ',actor,a['events'],'head/neck',round(a['return_head_step'],5),round(a['return_neck_step'],5))
print(json.dumps({k:v for k,v in checks.items() if k!='selected_player_steps'},indent=2))
