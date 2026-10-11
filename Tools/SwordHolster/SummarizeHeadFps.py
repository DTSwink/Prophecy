"""Summarize owned-PIE head/FPS captures without modifying the editor."""
import json
import math
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'Saved/Diagnostics/SwordHeadFps20261011'


def angle(a, b):
    a, b = a[-4:], b[-4:]
    dot = sum(x*y for x, y in zip(a, b))
    dot /= math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return math.degrees(2 * math.acos(min(1., abs(dot))))


def summary(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = data['rows']
    result = dict(name=path.stem, reason=data['reason'], count=len(rows),
                  dt_range=[min(r['dt'] for r in rows), max(r['dt'] for r in rows)], actors={})
    if 'wall' in rows[0]:
        intervals = [(b['wall']-a['wall'])/(b['tick']-a['tick']) for a,b in zip(rows,rows[1:])]
        result['wall_fps_median'] = 1/statistics.median(intervals)
        result['wall_fps_average'] = (rows[-1]['tick']-rows[0]['tick'])/(rows[-1]['wall']-rows[0]['wall'])
    for name in rows[0]['actors']:
        transitions, old = [], None
        for row in rows:
            fields = row['actors'][name]['fields']
            phase = fields.get('phase')
            if phase is None:
                continue
            if phase != old:
                transitions.append([row['tick'], phase, fields.get('pose_tick')])
                old = phase
        actor = dict(player=name == data['player'], transitions=transitions, windows={})
        for lo, hi in [(18,24),(25,89),(90,160),(161,260),(261,rows[-1]['tick'])]:
            window = [r for r in rows if lo <= r['tick'] <= hi]
            if len(window)<2:
                continue
            info = {}
            for channel in ['future', 'target', 'physical']:
                values = [(b['tick'],angle(a['actors'][name][channel]['head'], b['actors'][name][channel]['head'])) for a,b in zip(window,window[1:])]
                info[channel] = dict(peak=max(values,key=lambda x:x[1]), total=sum(v[1] for v in values))
            errors=[(r['tick'],angle(r['actors'][name]['target']['head'],r['actors'][name]['physical']['head'])) for r in window]
            info['tracking_error'] = dict(peak=max(errors,key=lambda x:x[1]),mean=statistics.mean(v[1] for v in errors))
            for bone in ['neck_01', 'neck_02', 'spine_05']:
                if bone not in window[0]['actors'][name]['target']:
                    continue
                values = [(b['tick'], angle(a['actors'][name]['target'][bone], b['actors'][name]['target'][bone]))
                          for a,b in zip(window,window[1:])]
                info['target_'+bone] = dict(peak=max(values,key=lambda x:x[1]),total=sum(v[1] for v in values))
            actor['windows'][f'{lo}-{hi}'] = info
        actor['head_body_socket_error_deg'] = max((angle(r['actors'][name]['physical']['head'],
            r['actors'][name]['native']['head']['pose']) for r in rows
            if r['actors'][name].get('native', {}).get('head')), default=None)
        result['actors'][name] = actor
    return result


if __name__ == '__main__':
    results = [summary(path) for path in sorted(OUT.glob('*.json')) if path.stem.startswith(('sim','kine'))]
    (OUT/'summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    if (OUT/'postflight.json').exists():
        receipt = dict(status='diagnosed; runtime correction not applied',
            scope='Current unsaved TestNN setup, owned PIE, numerical poses; no motion-viewing claim.',
            clock='All captured world deltas were 0.01666666567325592; FPS caps change pacing, not simulation delta in this fixed-60 setup.',
            source_defect=dict(file='Source/GameAnimationSample3/Private/ProphecySwordHolsterPose.cpp',
                live_head_index=15, live_head_parent_index=22,
                read_before_write=['BeginReturn ReturnWorld[parent]', 'BeginReturn PreviousWorld[parent]'],
                other_order_assumptions=['BodyPose', 'return parent angular rates', 'MountReturn', 'ReturnStep', 'AdvanceSpring'],
                consequence='Invalid head return inertia is redistributed into neck corrections despite the independent head angular cap.',
                historical='The pre-optimization LegacyBeginReturn has the same ordering defect.',
                test_gap='Lab/native parity fixture is parent-first; no parent index is greater than its child index.'),
            boundaries=['FPS alone has not been established as the trigger; cap-60 captures attained roughly 28-32 FPS on average.',
                'Repeated starts produced different neck commands at the same cap; low-cap runs also reproduced neck flips.',
                'Free head/neck angular limits at tick90 did not remove a 117-degree commanded neck flip.',
                'No saved PHAT, damping, collision, profile, Blueprint or map change; no native build or restart.',
                'kine-return is excluded: switching mode at90 canceled the active D/S at91.'],
            runs=[r for r in results if r['name']!='kine-return'],
            preservation=json.loads((OUT/'postflight.json').read_text(encoding='utf-8')))
        (ROOT/'Tools/SwordHolster/HeadFpsDiagnosis20261011.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    for d in results:
        print(d['name'],d['reason'],'dt',d['dt_range'],'fps',d.get('wall_fps_median'))
        for name,a in d['actors'].items():
            print(' ',name,'player',a['player'],'phases',a['transitions'])
            for w,v in a['windows'].items():
                print('  ',w, ' / '.join(f'{k}: max {x["peak"][1]:.2f}@{x["peak"][0]}'+(f' total {x["total"]:.1f}' if 'total' in x else f' mean {x["mean"]:.2f}') for k,x in v.items()))
