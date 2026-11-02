"""Counter-rotate the head after torso contact IK; never change other joints."""
from crawl_upper_cycle import *
import hashlib

def main():
 g=Geometry();path=OUT/'candidates/crawl.pkl';m=pickle.loads(path.read_bytes())
 backup=OUT/'before-head-reference-fix';backup.mkdir(exist_ok=True)
 if not (backup/'crawl.pkl').exists():
  shutil.copy2(path,backup/'crawl.pkl');shutil.copy2(path.with_suffix('.json'),backup/'crawl.json')
 old=pickle.loads((backup/'crawl.pkl').read_bytes())['frames'];f=old.copy()
 ref=interpolate(g,pickle.loads((OUT/'before/crawl.pkl').read_bytes())['frames'],4)
 op,orr=fk(g,old);rp,rr=fk(g,ref)
 f[:,9:12]=R.from_matrix(g.lr[2].T@orr[:,1].transpose(0,2,1)@rr[:,2]).as_rotvec()
 p,r=fk(g,f);dense=interpolate(g,f,32);rd=interpolate(g,ref,32)
 _,dr=fk(g,dense);_,drr=fk(g,rd);_,_,bottom=sample(g,dense)
 err=np.rad2deg(R.from_matrix(dr[:,2]@drr[:,2].transpose(0,2,1)).magnitude())
 report=dict(key_orientation_error_deg=float(np.rad2deg(R.from_matrix(r[:,2]@rr[:,2].transpose(0,2,1)).magnitude()).max()),dense_orientation_error_deg=float(err.max()),dense_head_joint_margin=float(joint_margins(g,dense,2).min()),floor_min_cm=float(bottom.min()*100),geometry=g.audit(f),head_position_unchanged=True,training_modified=False)
 assert report['key_orientation_error_deg']<1e-8 and err.max()<.02
 assert report['dense_head_joint_margin']>0 and bottom.min()>.0005
 assert report['geometry']['worst_penetration_cm']<.1
 assert np.array_equal(f[:,:9],old[:,:9]) and np.array_equal(f[:,12:],old[:,12:])
 assert np.allclose(p,op)
 m['frames']=f;path.write_bytes(pickle.dumps(m))
 j=json.loads(path.with_suffix('.json').read_text());j['head_reference_orientation']=report
 j['candidate_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
 j['description']='Head orientation matches the original reference at every keyframe; neck counterrotation cancels the extra torso tilt. Head position still follows the contact-corrected torso. Hands, knees and feet unchanged. This revision is preview-only; training still uses the previous version.'
 path.with_suffix('.json').write_text(json.dumps(j,indent=2))
 (OUT/'head-reference-orientation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
