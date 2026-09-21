import json,sys,pathlib,math
import numpy as np
from ReplayTemperedLeg import config,offsets,rot,unit,points
p=pathlib.Path(sys.argv[1]); results={}
for leg in (0,1):
    samples=[]
    for line in (p/'pipeline.jsonl').open():
        r=json.loads(line)
        if r['actor']!='BP_ProphecyManualPoseAgent_C_1' or r['attack'] or r['time']<1:continue
        s=np.array(r['published_lower']);h,k,a,t=points(s,leg)
        axis=unit(a-h);upper=k-h;bend=upper-axis*np.dot(upper,axis)
        if np.linalg.norm(bend)<.03:continue
        footforward=unit(np.array(config['ik_toe_offsets_m'][leg]))
        footup=np.array([1 if offsets[19+4*leg][0]<0 else -1,0,0])
        side=unit(np.cross(footup,footforward))@rot(s,12+16*leg);side[2]=0
        side=unit(side);oriented=np.cross(axis,side);confidence=np.linalg.norm(oriented)**2
        signed=np.dot(unit(bend),unit(oriented))
        samples.append(dict(time=r['time'],signed=float(signed),confidence=float(confidence),below_hip=bool(a[2]<h[2]),distance_cm=float(np.linalg.norm(a-h)*100)))
    results[str(leg)]=dict(samples=len(samples),backward=sum(s['signed']<0 for s in samples),
        backward_below_hip=sum(s['signed']<0 and s['below_hip'] for s in samples),
        worst=min(samples,key=lambda s:s['signed']) if samples else None)
print(json.dumps(results));(p/'signed-knee.json').write_text(json.dumps(results,indent=2))
