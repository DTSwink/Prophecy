"""Read-only dense validation and immutable originals for the contact review."""
import pickle,json,hashlib,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from clean_slow_contacts import Geometry,OUT,P,NAMES,sample,interpolate
g=Geometry();result={};backup=OUT/'before';backup.mkdir(exist_ok=True)
def seam(frames):
 p,r,_=sample(g,frames[[0,-1]]);d=p[1]-p[0];d[:,:2]-=p[1,0,:2]-p[0,0,:2]
 return dict(position_cm=float(np.linalg.norm(d,axis=1).max()*100),angle_deg=float(R.from_matrix(r[1]@r[0].transpose(0,2,1)).magnitude().max()*180/np.pi))
for name in NAMES:
 src=P/'motions'/f'{name}.pkl';path=OUT/'candidates'/src.name;j=json.loads(path.with_suffix('.json').read_text())
 if not (backup/src.name).exists():shutil.copy2(src,backup/src.name)
 assert hashlib.sha256((backup/src.name).read_bytes()).hexdigest()==j['source_sha256'],'Immutable original changed'
 old=pickle.loads((backup/src.name).read_bytes());new=pickle.loads(path.read_bytes());f=new['frames'];dense=interpolate(g,f,32);p,r,b=sample(g,dense)
 assert np.isfinite(f).all() and b.min()>-1e-5
 assert old['loop_mode']==new['loop_mode']==1
 assert abs((len(old['frames'])-1)/old['fps']-(len(f)-1)/new['fps'])<1e-9
 s0,s1=seam(old['frames']),seam(f)
 assert s1['position_cm']<s0['position_cm']+2,(name,'worsened loop seam',s0,s1)
 op,_,_=sample(g,old['frames']);same_old=old['frames'] if len(old['frames'])==len(f) else interpolate(g,old['frames'],round((len(f)-1)/(len(old['frames'])-1)))
 fp,_,_=sample(g,f);sp,_,_=sample(g,same_old)
 j.update(candidate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),after_min_cm=float(b.min()*100),dense_samples=len(dense),after_geometry=g.audit(f),
  max_body_displacement_cm=float(np.linalg.norm(fp-sp,axis=-1).max()*100),root_shift_cm=[float((f[:,2]-same_old[:,2]).min()*100),float((f[:,2]-same_old[:,2]).max()*100)],loop_seam_before=s0,loop_seam_after=s1)
 for body,n in enumerate(g.names):j['body_floor'][n].update(after_min_cm=float(b[:,g.gb==body].min()*100),after_max_cm=float(b[:,g.gb==body].min(1).max()*100))
 path.with_suffix('.json').write_text(json.dumps(j,indent=2));result[name]=j
 print(name,'floor cm',round(j['after_min_cm'],4),'seam cm',round(s1['position_cm'],2),flush=True)
(OUT/'report.json').write_text(json.dumps(result,indent=2))
(OUT/'validation.json').write_text(json.dumps(dict(contact_checks_passed=True,training_modified=False,validation='Exact training FK and quaternion interpolation, 32 subdivisions per key interval; unchanged duration and source hashes. Existing self-overlaps/limits remain separately reported.',motions={n:{k:j[k] for k in ['candidate_sha256','source_sha256','after_min_cm','dense_samples','loop_seam_after']} for n,j in result.items()}),indent=2))
