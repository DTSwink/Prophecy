import numpy as np
from scipy.spatial import cKDTree
b=np.load('boss_dump.npz'); al=np.load('align.npz'); sc,R,t=al['sc'],al['R'],al['t']
P=b['cow']; c=dict(np.load('corr.npz'))
for mat,am in ((4,30),(5,32),(6,31)):
    a=np.load(f'ada_m{am}.npz'); aw=(sc*(R@a['V'].T)).T+t
    auv=a['uv'][a['lay_uv']]; apos=a['lay_pos']
    sel=b['loopmat']==mat; bv=b['lv'][sel]; buv=b['uv'][sel]
    d,ii=cKDTree(auv).query(buv,k=8)
    choice={}
    for v,dr,ir in zip(bv,d,ii):
        cands=apos[ir][dr<=dr[0]+1e-3]
        side=np.sign(P[v,0])
        same=[x for x in cands if np.sign(aw[x,0])==side] or list(cands)
        best=min(same,key=lambda x:np.linalg.norm(aw[x]-P[v]))
        choice.setdefault(v,[]).append(best)
    bverts=np.array(sorted(choice)); avert=np.array([np.bincount(choice[v]).argmax() for v in bverts])
    pd=np.linalg.norm(aw[avert]-P[bverts],axis=1)
    print(mat,'verts',len(bverts),'unique',len(set(avert)),'pos dist mean/max',pd.mean(),pd.max())
    c[f'b{mat}']=bverts; c[f'a{mat}']=avert
np.savez('corr.npz',**c)
