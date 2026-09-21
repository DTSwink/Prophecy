import json
import math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent
reports = []
best = None
for path in sorted(root.glob('capture-*.json')):
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = data['rows']
    events = []
    for i in range(1, len(rows)):
        a, b = rows[i-1:i+1]
        speed = math.hypot(*b['mover_v'][:2])
        if speed < 20 or b['t'] < 5:
            continue
        direction = np.array([b['mover_v'][0]/speed, b['mover_v'][1]/speed, 0.0])
        steps = {k: float(np.dot(np.subtract(b[k], a[k]), direction))
                 for k in ('capsule', 'target', 'future', 'body', 'visible')}
        if min(steps['body'], steps['capsule'], steps['target']) >= -0.01:
            continue
        same_endpoint = float(np.linalg.norm(np.subtract(b['future'], a['future']))) < 1e-7
        event = {'i':i, 'time':b['t'], 'previous_dt_ms':a['dt']*1000,
                 'dt_ms':b['dt']*1000, 'alpha_before':a['alpha'], 'alpha_after':b['alpha'],
                 'mover_speed_cm_s':speed, 'same_endpoint':same_endpoint, **steps}
        event['capsule_prediction_error_cm'] = steps['capsule'] - (b['alpha']-a['alpha'])*speed/30
        for j in range(i-2, max(-1, i-9), -1):
            c = rows[j]
            if c['alpha'] < .999 and np.linalg.norm(np.subtract(c['future'], b['future'])) < 1e-7:
                previous_target = (np.array(c['target'])-c['alpha']*np.array(c['future']))/(1-c['alpha'])
                expected = previous_target+(np.array(b['future'])-previous_target)*b['alpha']
                event['reconstructed_target_error_cm'] = float(np.linalg.norm(expected-np.array(b['target'])))
                event['endpoint_span_cm'] = float(np.dot(np.array(b['future'])-previous_target,direction))
                break
        events.append(event)
        if same_endpoint and steps['body'] < -.1 and (best is None or steps['body'] < best[0]['body']):
            best = (event, rows, path.name, direction)
    errors = [np.linalg.norm(np.subtract(r['body'],r['visible'])) for r in rows]
    reports.append({'capture':path.name, 'frames':len(rows), 'start_time':rows[0]['t'], 'end_time':rows[-1]['t'],
                    'metadata':data['metadata'], 'body_visible_max_error_cm':float(max(errors)), 'events':events})
summary = {'captures':reports}
(root/'analysis.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps([{k:v for k,v in r.items() if k!='metadata'} for r in reports],indent=2))
if best:
    event, rows, source, direction = best
    event_t = event['time']
    window = [r for r in rows if event_t-.16 <= r['t'] <= event_t+.20]
    reference_row = rows[event['i']-1]
    origin = np.array(reference_row['body'])
    ts = np.array([r['t']-event_t for r in window])*1000
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig, axes = plt.subplots(2,1,figsize=(10,6.3),sharex=True,gridspec_kw={'height_ratios':[2.1,1]},layout='constrained')
    fig.suptitle('Captured backward pelvis step',fontsize=17,fontweight='bold',x=.08,ha='left')
    ax=axes[0]
    guide = [(r['t']-reference_row['t'])*event['mover_speed_cm_s'] for r in window]
    ax.plot(ts,guide,color='#2a995a',lw=2,label='Steady-speed guide (mover velocity)')
    ax.plot(ts,[np.dot(np.array(r['target'])-origin,direction) for r in window],color='#3570b1',ls='--',lw=1.6,marker='.',label='Target sent to Jolt')
    ax.plot(ts,[np.dot(np.array(r['body'])-origin,direction) for r in window],color='#d94444',lw=2,marker='o',ms=3,label='Simulated / displayed pelvis')
    ax.axvline(0,color='#8693a3',lw=1,ls=':')
    ax.annotate(f"{abs(event['body']):.2f} cm backward",xy=(0,event['body']),xytext=(40,event['body']-4),arrowprops={'arrowstyle':'->','color':'#d94444'},color='#b63232',fontweight='bold')
    ax.set_ylabel('Forward displacement (cm)')
    ax.legend(loc='upper left',frameon=False,fontsize=9)
    ax.grid(alpha=.18)
    ax.set_title(f"World time {event_t:.3f} s  |  {source}",fontsize=10,loc='left',color='#566070')
    ax=axes[1]
    ax.plot(ts,[r['alpha'] for r in window],color='#3570b1',marker='o',ms=3)
    ax.axvline(0,color='#8693a3',lw=1,ls=':')
    ax.set_ylim(-.05,1.12)
    ax.set_ylabel('Pose interpolation')
    ax.set_xlabel('Time relative to backward step (ms)')
    ax.grid(alpha=.18)
    ax.text(.98,.92,f"Frame time: {event['previous_dt_ms']:.2f} → {event['dt_ms']:.2f} ms\nInterpolation: {event['alpha_before']:.3f} → {event['alpha_after']:.3f}\nSame NN endpoint on both frames",transform=ax.transAxes,ha='right',va='top',fontsize=9,bbox={'facecolor':'white','edgecolor':'none','alpha':.9})
    fig.savefig(root/'pelvis-backward.png',dpi=170,facecolor='white')
    plt.close(fig)
    (root/'selected-event.json').write_text(json.dumps({'source':source,**event,'window':window},indent=2),encoding='utf-8')
