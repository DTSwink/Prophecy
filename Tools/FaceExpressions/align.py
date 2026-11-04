import numpy as np
from scipy.spatial import cKDTree
b=np.load('boss_dump.npz'); c=dict(np.load('corr.npz'))
P=b['cow']
def umeyama(src,dst):
    ms,md=src.mean(0),dst.mean(0); S=src-ms; D=dst-md
    U,s,Vt=np.linalg.svd(D.T@S/len(src)); d=np.sign(np.linalg.det(U@Vt)); E=np.diag([1,1,d])
    R=U@E@Vt; sc=(s*np.diag(E)).sum()/(S**2).sum()*len(src); t=md-sc*R@ms; return sc,R,t
ah=np.load('ada_m26.npz')['V']; bv,av=c['b7'],c['a7']
sc,R,t=umeyama(ah[av],P[bv])
fit=(sc*(R@ah[av].T)).T+t; err=np.linalg.norm(fit-P[bv],axis=1)
print('scale',sc,'R',np.round(R,3),'\nresid m mean/max',err.mean(),err.max(), 'boss head height m', np.ptp(P[bv][:,2]))
# positional match for eyeshell(5->m30) and eyelashes(6->m31)
for mat,am in ((5,30),(6,31)):
    a=np.load(f'ada_m{am}.npz')['V']; aw=(sc*(R@a.T)).T+t
    sel=b['loopmat']==mat; bverts=np.unique(b['lv'][sel])
    d,i=cKDTree(aw).query(P[bverts]); print(mat,'pos match mean/max m',d.mean(),d.max(),'unique',len(set(i)),len(bverts))
    c[f'b{mat}']=bverts; c[f'a{mat}']=i
np.savez('corr.npz',**c); np.savez('align.npz',sc=sc,R=R,t=t)
