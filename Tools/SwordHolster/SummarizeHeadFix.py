"""Summarize captured D/S return motion numerically; no editor/asset changes."""
import json
import math
from pathlib import Path

root=Path(__file__).resolve().parents[2]
out=root/'Saved/Diagnostics/SwordHeadFix20261011'

def angle(a,b):
    a,b=a[3:],b[3:]
    dot=abs(sum(x*y for x,y in zip(a,b)))/math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return math.degrees(2*math.acos(min(1,dot)))

def summarize(path):
    data=json.loads(path.read_text(encoding='utf-8'));rows=data['rows']
    result=dict(reason=data['reason'],cap=data['options']['fps'],rows=len(rows),
        actual_fps=(rows[-1]['tick']-rows[0]['tick'])/(rows[-1]['wall']-rows[0]['wall']),
        world_deltas=sorted(set(r['dt'] for r in rows)),draw_results=data.get('draw_results'),actors={})
    for name in rows[0]['actors']:
        actor=dict(events=[],returns=[],finite=True);previous=None;last_phase=None;segment=None
        for row in rows:
            current=row['actors'][name];phase=current['fields']['phase']
            if phase!=last_phase:
                actor['events'].append([row['tick'],phase]);last_phase=phase
                if phase==4:
                    segment=dict(start=row['tick'],end=None,steps={},tracking_degrees=0);actor['returns'].append(segment)
                elif segment and segment['end'] is None:
                    segment['end']=row['tick']
            for source in ['target','future','physical']:
                actor['finite'] &= all(math.isfinite(v) for p in current[source].values() for v in p)
            if segment and segment['end'] is None:
                segment['tracking_degrees']=max(segment['tracking_degrees'],angle(current['target']['head'],current['physical']['head']))
                if previous:
                    for source in ['target','future','physical']:
                        for bone in ['neck_01','neck_02','head']:
                            key=source+'_'+bone
                            value=angle(previous[source][bone],current[source][bone])
                            segment['steps'][key]=max(segment['steps'].get(key,0),value)
            previous=current
        result['actors'][name]=actor
    return result

result={p.stem:summarize(p) for p in sorted(out.glob('sim*.json')) if 'summary' not in p.stem}
(out/'motion-summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
if result:
    reference=json.loads((out/'sim60-a.json').read_text(encoding='utf-8'))['rows']
    identical=True;max_degrees=0.;max_cm=0.;poses_identical=True
    for name in result:
        rows=json.loads((out/(name+'.json')).read_text(encoding='utf-8'))['rows']
        identical &= len(rows)==len(reference) and all(a['tick']==b['tick'] and a['actors']==b['actors'] for a,b in zip(rows,reference))
        for a,b in zip(rows,reference):
            for actor in a['actors']:
                for source in ['target','future','physical']:
                    for bone,pose in a['actors'][actor][source].items():
                        other=b['actors'][actor][source][bone];poses_identical &= pose==other
                        max_degrees=max(max_degrees,0 if pose[3:]==other[3:] else angle(pose,other))
                        max_cm=max(max_cm,math.dist(pose[:3],other[:3]))
    checks=dict(runs=len(result),all_captures_complete=all(v['reason']=='captured' and v['rows']==323 for v in result.values()),
        all_draw_requests_accepted=all(all(ok for _,ok in v['draw_results']) for v in result.values()),
        all_actor_samples_identical=identical,
        all_pose_samples_identical=poses_identical,max_repeat_pose_difference_degrees=max_degrees,max_repeat_position_difference_cm=max_cm,
        action_ticks_identical=all(a['events']==result['sim60-a']['actors'][name]['events'] for v in result.values() for name,a in v['actors'].items()),
        all_cycles_complete=all(len(a['returns'])==2 and all(r['end'] is not None for r in a['returns']) and a['finite'] for v in result.values() for a in v['actors'].values()))
    checks['max_return_step_degrees']={key:max(r['steps'][key] for v in result.values() for a in v['actors'].values() for r in a['returns'])
        for key in ['target_neck_01','target_neck_02','target_head','physical_head']}
    (out/'matrix-checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    assert checks['all_captures_complete'] and checks['all_draw_requests_accepted'] and checks['all_cycles_complete']
for name,run in result.items():
    print(name,'FPS',round(run['actual_fps'],2),'delta',run['world_deltas'],'reason',run['reason'])
    for actor,data in run['actors'].items():
        print(' ',actor,'events',data['events'],'finite',data['finite'])
        for r in data['returns']:
            print('   return',r['start'],r['end'],{k:round(v,5) for k,v in r['steps'].items()},'head tracking',round(r['tracking_degrees'],5))
