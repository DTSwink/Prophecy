"""Compare the unchanged prefix and cut-joint error in owned diagnostic runs."""
import json, math, pathlib, re
import numpy as np
out=pathlib.Path(__file__).resolve().parents[2]/'Saved/Diagnostics/PikeSlide'
def rotate(q,v):
    x=np.array(q[:3]);v=np.array(v)
    return v+2*np.cross(x,np.cross(x,v)+q[3]*v)
def value(s,key):
    return np.array([float(x) for x in re.search(key+r'=\(X=([^,]+),Y=([^,]+),Z=([^\)]+)\)',s).groups()])
def analyze(path):
    capture=json.loads(path.read_text());assert not capture['error'],capture['error']
    rows=[];frames=set()
    for row in capture['samples']:
        for joint in row['joints']:
            a,b=joint['bodies'];s=joint['instance']
            anchors=[np.array(body['p'])+rotate(body['q'],value(s,'Pos'+str(i+1))) for i,body in enumerate([a,b])]
            x,y=[rotate(b['q'],value(s,key+'2')) for key in ('PriAxis','SecAxis')]
            x1,y1=[rotate(a['q'],value(s,key+'1')) for key in ('PriAxis','SecAxis')]
            z,z1=np.cross(x,y),np.cross(x1,y1);delta=anchors[0]-anchors[1]
            angle=math.degrees(math.acos(np.clip((np.dot(x,x1)+np.dot(y,y1)+np.dot(z,z1)-1)/2,-1,1)))
            frames.add(tuple(float(v) for key in ('Pos1','Pos2','PriAxis1','PriAxis2','SecAxis1','SecAxis2') for v in value(s,key)))
            rows.append({'t':row['t'],'lateral_cm':float(np.linalg.norm([np.dot(delta,x),np.dot(delta,y)])),
                         'angular_deg':angle,'axial_cm':float(np.dot(delta,z))})
    return {'samples':len(capture['samples']),'joint_samples':len(rows),'distinct_frames':len(frames),
            'max_lateral_cm':max(r['lateral_cm'] for r in rows),'max_angular_deg':max(r['angular_deg'] for r in rows),
            'rms_lateral_cm':math.sqrt(sum(r['lateral_cm']**2 for r in rows)/len(rows)),
            'rms_angular_deg':math.sqrt(sum(r['angular_deg']**2 for r in rows)/len(rows)), 'rows':rows},capture
baseline,base=analyze(out/'probe.json')
result={'baseline':baseline}
trials=sorted(out.glob('probe-iterations-*.json'))
if (out/'probe-wound-anchor.json').exists(): trials.append(out/'probe-wound-anchor.json')
for path in trials:
    data,capture=analyze(path)
    before=[r['sword'] for r in base['samples'] if r['t']<=baseline['rows'][0]['t']]
    comparison=[r['sword'] for r in capture['samples'] if r['t']<=baseline['rows'][0]['t']]
    data['same_prefix']=before==comparison
    shifts=[math.sqrt(sum(x*x for x in j['projection_cm'])) for r in capture['samples'] for j in r['joints'] if 'projection_cm' in j]
    if shifts: data['max_projection_per_frame_cm']=max(shifts)
    result[path.stem]=data
(out/'analysis.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:{x:y for x,y in v.items() if x!='rows'} for k,v in result.items()},indent=2))
