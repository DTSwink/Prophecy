import json,sys,numpy as np
from pathlib import Path
d=json.loads(Path(sys.argv[1] if len(sys.argv)>1 else 'Saved/Diagnostics/SlashReturnVariants-20260923-134217.json').read_text())
out=[]
for r in d['rows']:
    if r['agent']!='BP_ProphecyManualPoseAgent_C_1' or not 758<=r['frame']<=810:continue
    b=r['bones'];v=lambda n:np.array(b[n][0][:3]);up=v('neck_01')-v('pelvis');up/=np.linalg.norm(up)
    right=v('upperarm_r')-v('upperarm_l');w=np.linalg.norm(right)/2;right-=up*np.dot(up,right);right/=np.linalg.norm(right)
    m=np.stack([np.cross(right,up),right,up]);o=(v('upperarm_r')+v('upperarm_l'))/2
    e=m@(v('lowerarm_r')-o);h=m@(v('hand_r')-o);score=1000
    for t in np.linspace(0,1,101):
        p=e+(h-e)*t
        if -40<p[2]<0:score=min(score,(p[0]/(w*.7))**2+(p[1]/(w*.65))**2)
    out.append({'frame':r['frame'],'state':r['state'],'elbow':np.round(e,2).tolist(),'hand':np.round(h,2).tolist(),'score':score})
print(json.dumps(sorted(out,key=lambda x:x['score'])[:12],indent=1))
