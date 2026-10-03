import json,math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
p=Path('Saved/Diagnostics/PikeReturn')
def load(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert d['reason']=='Complete',d['reason']
 return {r['frame'] if 'variants' in tag else r['tick']:r for r in d['rows'] if r['possessed']}
def unit(v):return v/np.linalg.norm(v)
def torso(b):
 v=lambda n:np.array(b[n]['p']);z=unit(v('neck_01')-v('pelvis'));y=v('upperarm_r')-v('upperarm_l');width=np.linalg.norm(y)/2;y=unit(y-z*np.dot(y,z))
 return (v('upperarm_r')+v('upperarm_l'))/2,R.from_matrix(np.stack([np.cross(y,z),y,z],axis=1)),width
def local(row,kind):
 b={n:v[kind] for n,v in row['pose'].items()};o,q,w=torso(b)
 return q.inv().apply(np.array(b['hand_r']['p'])-o),q.inv()*R.from_quat(b['hand_r']['q']),w
def geometry(row):
 b=row['weapon'];lo=np.array(b['min']);hi=np.array(b['max']);scale=np.array(b['scale']);i=int(np.argmax(hi-lo));a=(lo+hi)/2;c=a.copy();a[i]=lo[i];c[i]=hi[i]
 q=R.from_quat(b['grip']['q']);offset=np.array(b['grip']['p'])
 pad=np.linalg.norm(((hi-lo)*scale/2)[[j for j in range(3) if j!=i]])+1
 return offset+q.apply(a*scale),offset+q.apply(c*scale),pad
def clearance(h,q,w,a,b,pad):
 a=h+q.apply(a);d=h+q.apply(b)-a;lo=0.;hi=1.;bottom=-3*w-pad;top=.7*w+pad
 if abs(d[2])<1e-8:
  if a[2]<bottom or a[2]>top:return 1e6
 else:
  ts=sorted([(bottom-a[2])/d[2],(top-a[2])/d[2]]);lo=max(0,ts[0]);hi=min(1,ts[1])
  if lo>hi:return 1e6
 radii=np.array([.9*w+pad,w+pad]);v=d[:2]/radii;c=a[:2]/radii;t=np.clip(-c@v/max(1e-12,v@v),lo,hi)
 return float((c+v*t)@(c+v*t))
a,b=load('legacy'),load('smooth');end=next(t for t in sorted(a) if t>90 and a[t]['attack']=='None')
maxprefix=max(float(np.linalg.norm(np.array(v['future']['p'])-b[t]['pose'][n]['future']['p'])) for t in a if t<end for n,v in a[t]['pose'].items())
result={'end':end,'prefix_max_cm':maxprefix,'variants':{}}
for tag,data in [('legacy',a),('smooth',b)]:
 points=np.array([local(data[t],'presented')[0] for t in range(end,180)])
 speed=np.linalg.norm(np.diff(points,axis=0),axis=1);accel=np.linalg.norm(np.diff(points,n=2,axis=0),axis=1)
 chord=points[-1]-points[0];along=np.clip((points-points[0])@chord/(chord@chord),0,1);detour=np.linalg.norm(points-(points[0]+along[:,None]*chord),axis=1)
 minimum=1e6;minimum_post4=1e6
 for t in range(end,180):
  h,q,w=local(data[t],'presented');ph,pq,pw=local(data[t-1],'presented');base,tip,pad=geometry(data[t]);interp=Slerp([0,1],R.from_quat([pq.as_quat(),q.as_quat()]))
  for alpha in np.linspace(0,1,9):
   score=clearance(ph+(h-ph)*alpha,interp(alpha),pw+(w-pw)*alpha,base,tip,pad);minimum=min(minimum,score)
   if t>end+4:minimum_post4=min(minimum_post4,score)
 result['variants'][tag]=dict(path_cm=float(sum(speed)),max_step_cm=float(max(speed)),max_velocity_change_cm_per_tick=float(max(accel)),max_detour_cm=float(max(detour)),swept_blade_clearance=minimum,post4_swept_blade_clearance=minimum_post4,samples=[dict(tick=t,hand=local(data[t],'presented')[0].tolist()) for t in [end,125,130,140,150,160,170,179]])
print(json.dumps(result,indent=2));(p/'summary.json').write_text(json.dumps(result,indent=2))
