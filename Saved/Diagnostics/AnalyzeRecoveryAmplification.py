import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics')
d=json.loads((p/'KneeHistoricalBaseline-capture.json').read_text(encoding='utf-8'))['rows']
def u(x):return x/max(np.linalg.norm(x),1e-12)
def a(x,y):return np.degrees(np.arccos(np.clip(u(x)@u(y),-1,1)))
ref=None
last=None
for r in d:
    bones=r['targets']; side='r'
    for mode in ('previous','future'):
        h,k,f=[np.array(bones[n+'_'+side][mode]['p']) for n in ('thigh','calf','foot')]
        q=R.from_quat(bones['thigh_'+side][mode]['q']); upper=k-h;lower=f-k;axis=u(f-h);rad=upper-axis*(upper@axis)
        if ref is None or np.linalg.norm(f-h)<=np.linalg.norm(upper)+np.linalg.norm(lower)-1:
            ref=q.inv().apply(u(rad))
    # Simple interpolation positions; target rotation used only for stable frame.
    alpha=bones['thigh_r']['alpha']
    h,k,f=[(1-alpha)*np.array(bones[n+'_r']['previous']['p'])+alpha*np.array(bones[n+'_r']['future']['p']) for n in ('thigh','calf','foot')]
    axis=u(f-h);rad=k-h-axis*((k-h)@axis)
    stable=R.from_quat(bones['thigh_r']['target']['q']).apply(ref);stable=u(stable-axis*(stable@axis))
    hh,kk,ff=[np.array(bones[n+'_r']['target']['p']) for n in ('thigh','calf','foot')];ax=u(ff-hh);rr=kk-hh-ax*((kk-hh)@ax)
    if 169<=r['clock']<=180:
        print(r['clock'],'raw radius',round(np.linalg.norm(rad),4),'final',round(np.linalg.norm(rr),4),'raw vs stable',round(a(rad,stable),2),'final vs stable',round(a(rr,stable),2),'stable step',round(a(stable,last),2) if last is not None else 0)
    last=stable
