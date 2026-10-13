"""Read-only repeated D/S boundary measurements in pelvis-translation coordinates."""
import json, pathlib, sys
import numpy as np

root = pathlib.Path('Saved/Diagnostics/ReachGrasp20261012')
name = sys.argv[1] if len(sys.argv)>1 else 'repeated-sim'
data = json.loads((root/(name+'.json')).read_text(encoding='utf-8'))
rows=data['rows']
def angle(a,b):
    return float(np.degrees(2*np.arccos(np.clip(abs(np.dot(a,b)),0,1))))
out={'reason':data['reason'],'actors':{}}
for actor in rows[-1]['actors']:
    events=[]; metrics=[]; previous=None
    for row in rows:
        a=row['actors'][actor]; f=a['fields']; phase=int(f['phase'])
        m={'tick':row['tick'],'phase':phase,'fields':f}
        if previous:
            old=previous['actors'][actor]
            if phase!=int(old['fields']['phase']):events.append({'tick':row['tick'],'from':int(old['fields']['phase']),'to':phase})
            for kind in ['target','physical','future']:
                h=np.array(a[kind]['hand_r']);p=np.array(a[kind]['pelvis']);h0=np.array(old[kind]['hand_r']);p0=np.array(old[kind]['pelvis'])
                m[kind+'_cm']=float(np.linalg.norm((h[:3]-p[:3])-(h0[:3]-p0[:3])))
                m[kind+'_deg']=angle(h[3:],h0[3:])
            m['tracking_cm']=float(np.linalg.norm(np.array(a['target']['hand_r'][:3])-a['physical']['hand_r'][:3]))
            for key in a.get('equipment',{}):
                if key in old['equipment']:m[key+'_deg']=angle(a['equipment'][key][3:],old['equipment'][key][3:])
        metrics.append(m);previous=row
    windows=[]
    for e in events:
        if (e['from'],e['to']) in [(1,2),(2,4)]:
            t=e['tick'];window=[m for m in metrics if t-8<=m['tick']<=t+8]
            windows.append({'event':e,'samples':window})
    out['actors'][actor]={'events':events,'windows':windows}
    print(actor, events)
    for w in windows:
        e=w['event'];t=e['tick'];before=[m for m in w['samples'] if m['tick']<t];after=[m for m in w['samples'] if m['tick']>=t]
        print(' boundary',e,'peak-before',[(k,round(max(m.get(k,0) for m in before),3)) for k in ['target_cm','target_deg','physical_cm','physical_deg']], 'peak-after',[(k,round(max(m.get(k,0) for m in after),3)) for k in ['target_cm','target_deg','physical_cm','physical_deg']])
(root/(name+'-boundaries.json')).write_text(json.dumps(out,indent=2),encoding='utf-8')
print('authored keys',next((list(r['actors'][actor]['authored']) for r in rows if r['actors'][actor].get('authored')),[]))
