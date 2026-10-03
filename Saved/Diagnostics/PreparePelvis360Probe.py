from pathlib import Path
p=Path('Saved/Diagnostics')
s=(p/'ReplayPelvis360.py').read_text().split('result=[]')[0]
s+='''
from scipy.spatial.transform import Rotation as R
from ReplayTemperedLeg import unit, points, offsets
f=369;x=np.array(rows[f]['lower_input']);pr=rows[f-2];pub=np.array(pr['published_lower']);prev=np.array(rows[f-4]['published_lower']);raw=clean(np.array(pr['lower_input'][:41])+pr['lower_delta'][:41]);o=25
h,k,a,t=points(pub,1);oldh,oldk,olda,oldt=points(prev,1);axis=unit(a-h);oa=unit(olda-oldh);op=unit(oldk-oldh-oa*np.dot(oldk-oldh,oa));change=rot(prev,o+3).T@rot(pub,o+3);ca=oa@change;cp=op@change;c0=np.clip(ca@axis,-1,1);transport=cp-(ca+axis)*np.dot(cp,axis)/max(1e-6,1+c0);fr=unit(transport-axis*np.dot(transport,axis));up=k-h;pole=unit(up-axis*np.dot(up,axis));ang=np.arctan2(np.dot(axis,np.cross(fr,pole)),np.clip(fr@pole,-1,1));print('foot-relative extra steering at367',np.degrees(ang))
variants={'baseline':pub}
for cap in (3,6,12):
 z=pub.copy();correction=np.clip(ang,-np.radians(cap),np.radians(cap))-ang;z[34:40]=(rot(pub,34)@R.from_rotvec(axis*correction).as_matrix().T)[:2].ravel();variants['pole_cap_'+str(cap)]=z
# Keep the exact ankle and bend direction; vary only the allowed calf length.
for extra in (.005,.01,.02):
 z=pub.copy();L1=np.linalg.norm(up);L2=np.linalg.norm(a-k)+extra;dist=np.linalg.norm(a-h);along=(L1*L1-L2*L2+dist*dist)/(2*dist);newup=axis*along+pole*np.sqrt(max(0,L1*L1-along*along));normal=unit(np.cross(axis,pole));ob=np.array([unit(up),unit(np.cross(normal,unit(up))),normal]);nb=np.array([unit(newup),unit(np.cross(normal,unit(newup))),normal]);z[34:40]=(rot(pub,34)@ob.T@nb)[:2].ravel();variants['calf_extra_cm_'+str(extra*100)]=z
inputs=[]
for name,z in variants.items():
 v=x.copy();carry=rot(pub,34).T@rot(x,34);v[34:40]=(rot(z,34)@carry)[:2].ravel();v[110:116]=(v[34:40]-v[75:81])/c['pose_delta_scale_final'];inputs.append(v)
y=predict(inputs);print({name:(out[:3]*100).tolist() for name,out in zip(variants,y)})
'''
(p/'ProbePelvis360Correction.py').write_text(s)
