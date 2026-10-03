import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics/Knee202')
records=[json.loads(x) for x in Path('Saved/Diagnostics/RecoveryPoleSmoothing.jsonl').read_text(encoding='utf-8-sig').splitlines()]
start=0
for i in range(1,len(records)):
    if records[i]['time']<records[i-1]['time']-1.e-5:start=i
records=records[start:];(p/'kick_current_pole_trace.json').write_text(json.dumps(records))
def unit(x):return x/max(np.linalg.norm(x),1.e-12)
def mat(s,o):
    a=unit(np.array(s[o:o+3]));b=np.array(s[o+3:o+6]);b=unit(b-a*(a@b));return np.array([a,b,np.cross(a,b)])
def pole(s,x):
    o=x['offset'];h=np.array(s[:3])+np.array(x['hip'])@mat(s,3);u=np.array(x['knee'])@mat(s,o+9)
    axis=unit(np.array(s[o:o+3])-h);rad=u-axis*(u@axis);return unit(rad),np.linalg.norm(rad),u,axis
def angle(a,b):return np.degrees(np.arccos(np.clip(a@b,-1,1)))
print('run records',len(records),'times',records[0]['time'],records[-1]['time'])
for x in records:
    tick=round(x['time']*60)
    if not(165<=tick<=175 or 199<=tick<=215):continue
    old,before,after=[pole(x[k],x) for k in ['previous','before','after']];o=x['offset']
    qold,qpre,qpost=[R.from_matrix(mat(x[k],o+9).T) for k in ['previous','before','after']]
    print(tick,'L' if o==9 else 'R','candidatePole/acceptedPole/thighBefore/thighAfter/radius',*[round(v,3) for v in [angle(old[0],before[0]),angle(old[0],after[0]),np.degrees((qold.inv()*qpre).magnitude()),np.degrees((qold.inv()*qpost).magnitude()),after[1]*100]])
