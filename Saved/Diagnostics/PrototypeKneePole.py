import json,numpy as np
from scipy.spatial.transform import Rotation
data=json.load(open('Saved/Diagnostics/CalfAnkleConnection-knee617-before.json'))
rows=[r for r in data['rows'] if r['possessed']]
def geo(r,s,kind):
    p=np.array([r['targets'][b+'_'+s][kind]['p'] for b in ('thigh','calf','foot')])
    h,k,f=p;u=k-h;v=f-k;d=np.linalg.norm(f-h);axis=(f-h)/d
    return p,np.linalg.norm(u),np.linalg.norm(v),d,axis,u-axis*np.dot(u,axis)
for s in ('l','r'):
    local=None;last=None;entries=[]
    for r in rows:
        for kind in ('previous','future'):
            p,a,b,d,axis,pole=geo(r,s,kind)
            if np.linalg.norm(pole)>1e-5 and (local is None or d<=a+b-4):
                local=Rotation.from_quat(r['targets']['thigh_'+s][kind]['q']).inv().apply(pole/np.linalg.norm(pole))
        p,a,b,d,axis,pole=geo(r,s,'target');h,k,f=p;old=k.copy()
        if d>a+b-4:
            nd=a+b-4*np.exp(-(d-(a+b-4))/4);along=(a*a-b*b+nd*nd)/(2*nd);radius=np.sqrt(max(0,a*a-along*along))
            if local is not None:
                ref=Rotation.from_quat(r['targets']['thigh_'+s]['target']['q']).apply(local);ref-=axis*np.dot(ref,axis);ref/=np.linalg.norm(ref)
                pole+=ref*(max(0,-np.dot(pole,ref))+max(0,radius-np.linalg.norm(pole)))
            k=h+axis*along+pole/np.linalg.norm(pole)*radius
        dirs=[(old-h)/a,(k-h)/a]
        if last is not None:
            angles=[np.degrees(np.arccos(np.clip(np.dot(x,y),-1,1))) for x,y in zip(dirs,last)]
            entries.append([round(r['t']*60),*angles,angles[1]-angles[0]])
        last=dirs
    print(s,sorted(entries,key=lambda x:x[-1],reverse=True)[:8])
    print('event',[e for e in entries if e[0] in (456,457,458,618,619)])
