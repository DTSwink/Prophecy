"""Compare the two owned captures; no Unreal access or asset mutations."""
import json,math,pathlib,re
import numpy as np
out=pathlib.Path(__file__).resolve().parents[2]/'Saved/Diagnostics/CoupledPike'
def rotate(q,v):
    a=np.array(q[:3]);v=np.array(v)
    return v+2*np.cross(a,np.cross(a,v)+q[3]*v)
def value(s,key):
    return np.array([float(x) for x in re.search(key+r'=\(X=([^,]+),Y=([^,]+),Z=([^\)]+)\)',s).groups()])
result={};prefixes=[]
for mode in ('off','coupled'):
    capture=json.loads((out/('probe-'+mode+'.json')).read_text())
    assert not capture['error'],capture['error']
    rows=[]
    for row in capture['samples']:
        for joint in row['joints']:
            a,b=joint['bodies'];s=joint['instance']
            anchors=[np.array(body['p'])+rotate(body['q'],value(s,'Pos'+str(i+1))) for i,body in enumerate([a,b])]
            x,y=[rotate(b['q'],value(s,key+'2')) for key in ('PriAxis','SecAxis')]
            x1,y1=[rotate(a['q'],value(s,key+'1')) for key in ('PriAxis','SecAxis')]
            z,z1=np.cross(x,y),np.cross(x1,y1);delta=anchors[0]-anchors[1]
            angle=math.degrees(math.acos(np.clip((np.dot(x,x1)+np.dot(y,y1)+np.dot(z,z1)-1)/2,-1,1)))
            rows.append(dict(t=row['t'],lateral_cm=float(np.linalg.norm([np.dot(delta,x),np.dot(delta,y)])),
                angle_deg=angle,axial_cm=float(np.dot(delta,z))))
    assert rows,'No cut captured'
    prefixes.append([r['sword'] for r in capture['samples'] if r['t']<=rows[0]['t']])
    result[mode]=dict(first_cut=rows[0]['t'],samples=len(rows),peak_cm=max(r['lateral_cm'] for r in rows),
        rms_cm=math.sqrt(sum(r['lateral_cm']**2 for r in rows)/len(rows)),peak_angle=max(r['angle_deg'] for r in rows),rows=rows)
result['identical_precontact_prefix']=prefixes[0]==prefixes[1]
(out/'comparison.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:({a:b for a,b in v.items() if a!='rows'} if isinstance(v,dict) else v) for k,v in result.items()},indent=2))
