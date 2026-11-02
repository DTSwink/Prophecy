"""Resolve the equivalent knee-pole solutions cyclically, not from a cold start."""
import json,pickle,hashlib,time
import numpy as np
from clean_slow_contacts import *
g=Geometry();path=OUT/'candidates/crawl.pkl';m=pickle.loads(path.read_bytes());frames=m['frames'];old=pickle.loads((P/'motions/crawl.pkl').read_bytes())['frames'].astype(float);old=interpolate(g,old,4)
ps,rs,bs,root,targets=plan(g,'crawl',old);ids=np.arange(6+g.k.get_joint(9).dof_idx,6+g.k.get_joint(12).dof_idx)
started=time.time()
for cycle in range(2):
 previous=frames[-1,ids]-old[-1,ids];result=[]
 for i,f in enumerate(frames):
  knee=ps[i,10].copy();knee[2]+=max(0,C-bs[i,np.isin(g.gb,[9,10])].min())
  new,previous=chain(g,f,old[i],9,C,ps[i,11,:2],knee,rs[i],previous);result.append(new)
 frames=np.array(result);p,r,b=sample(g,frames[[0,-1]]);delta=p[1,10]-p[0,10];delta[:2]-=p[1,0,:2]-p[0,0,:2];seam=np.linalg.norm(delta)
 print('cycle',cycle,'knee seam cm',seam*100,'seconds',time.time()-started,flush=True)
 if seam<.03:break
assert seam<.03,seam
dense=interpolate(g,frames,32);_,_,db=sample(g,dense);extra=np.zeros(len(frames))
for i in range(len(frames)-1):extra[i:i+2]=np.maximum(extra[i:i+2],max(0,.0005-db[i*32:(i+1)*32+1].min()))
assert extra.max()<.006
frames[:,2]+=extra;path.write_bytes(pickle.dumps(dict(m,frames=frames)))
j=json.loads(path.with_suffix('.json').read_text());j.update(candidate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),cyclic_knee_seam_cm=seam*100,after_geometry=g.audit(frames));path.with_suffix('.json').write_text(json.dumps(j,indent=2))
