import numpy as np
from scipy.spatial import cKDTree
b=np.load('boss_dump.npz')
parts={7:26,1:27,2:28,3:29,4:30,6:31,5:32}  # boss material -> ada lod3 mesh
res={}
for mat,am in parts.items():
    a=np.load(f'ada_m{am}.npz')
    sel=b['loopmat']==mat
    bv=b['lv'][sel]; buv=b['uv'][sel]
    auv=a['uv'][a['lay_uv']]; apos=a['lay_pos']
    best=None
    for flip in (False,True):
        q=buv.copy()
        if flip: q[:,1]=1-q[:,1]
        d,i=cKDTree(auv).query(q)
        if best is None or d.mean()<best[0]: best=(d.mean(),flip,d,i)
    dm,flip,d,i=best
    # per boss vertex -> ada vertex (majority)
    mp={}
    for v,ai in zip(bv,apos[i]): mp.setdefault(v,[]).append(ai)
    bverts=np.array(sorted(mp)); avert=np.array([np.bincount(mp[v]).argmax() for v in bverts])
    amb=sum(len(set(mp[v]))>1 for v in bverts)
    print(b['mats'][mat],'flip',flip,'uv dist mean/max',d.mean(),d.max(),'bverts',len(bverts),'unique ada',len(set(avert)),'ada n',len(a['V']),'ambiguous',amb)
    res[mat]=(bverts,avert)
np.savez('corr.npz',**{f'b{m}':v[0] for m,v in res.items()},**{f'a{m}':v[1] for m,v in res.items()})
