"""Decode consequences of replacing solved thigh twist with NN twist."""
import pathlib,runpy,json,numpy as np
from scipy.spatial.transform import Rotation
D=runpy.run_path(str(pathlib.Path(__file__).with_name('RecoveryCandidateReview.py')))
globals().update({k:D[k] for k in ['root','off','walk','rows','unit','project','rot','aa','angle']})
def minimal(a,b):
 a=unit(a);b=unit(b);cross=np.cross(a,b);sn=np.linalg.norm(cross);co=np.clip(np.dot(a,b),-1,1)
 return aa(cross,np.arctan2(sn,co)) if sn>1e-10 else np.eye(3)
def calf(thigh,k,kc,p,pc,tofoot):
 lm=unit(kc);lh=unit(np.cross(lm,pc));tm=unit(k);wh=unit(np.cross(tm,p))@thigh;wm=unit(tofoot)
 ws=unit(np.cross(wh,wm));wn=unit(np.cross(wm,ws));ws=unit(np.cross(wn,wm));ls=unit(np.cross(lh,lm))
 return np.array([lm,ls,unit(np.cross(lm,ls))]).T@np.array([wm,ws,wn])
out=[]
for t in range(149,180,2):
 s=np.array(rows[t]['published_lower']);raw=np.array(rows[t]['lower_input'][:41])+rows[t]['lower_delta'][:41]
 rec={'tick':t,'legs':{}}
 for i,name in enumerate(['left','right']):
  o=9+16*i;h=17+4*i;k=off[h+1];kc=off[h+2];p,pc=np.array(walk['ik_local_pole_axes'][i]);sr=rot(s[o+9:o+15]);rr=rot(raw[o+9:o+15])
  aligned=rr@minimal(k@rr,k@sr);hip=s[:3]+off[h]@rot(s[3:9]);knee=hip+k@sr;tofoot=s[o:o+3]-knee
  oldcalf=calf(sr,k,kc,p,pc,tofoot);newcalf=calf(aligned,k,kc,p,pc,tofoot)
  geom=unit(np.cross(k@sr,tofoot));encoded=unit(np.cross(unit(k),p))@sr;newencoded=unit(np.cross(unit(k),p))@aligned
  rec['legs'][name]={'thigh_twist_change_deg':angle(sr,aligned),'calf_rotation_change_deg':angle(oldcalf,newcalf),'knee_change_cm':float(np.linalg.norm(k@sr-k@aligned)*100),
   'old_hinge_vs_actual_kneeplane_deg':float(np.degrees(np.arccos(np.clip(abs(np.dot(geom,encoded)),-1,1)))),
   'new_hinge_vs_actual_kneeplane_deg':float(np.degrees(np.arccos(np.clip(abs(np.dot(geom,newencoded)),-1,1)))),
   'old_calffk_ankle_error_cm':float(np.linalg.norm(kc@oldcalf-tofoot)*100),'new_calffk_ankle_error_cm':float(np.linalg.norm(kc@newcalf-tofoot)*100),
   'new_hinge_calf_cross_magnitude':float(np.linalg.norm(np.cross(newencoded,unit(tofoot))))}
 out.append(rec)
path=root/'Saved/Diagnostics/RecoveryCandidateReviewTwist.json';path.write_text(json.dumps(out,indent=2))
print('TWIST_REVIEW',path)
for r in out:
 print(r['tick'],{n:{k:round(v,3) for k,v in d.items()} for n,d in r['legs'].items()})
