"""Show the worst current-PHAT shoulder target and nearest admissible rotation."""
import json, os, pickle, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitCrawl/upperarm-pose-audit'
sys.path.insert(0,str(ROOT/'Labs/MimicKitUEFN'))
sys.path.insert(0,str(ROOT/'Labs/RoboticCrawlAE'))
from fit_motion_limits import sampled_coordinates, MJCFCharModel
from test_model import coords
from current_phat import verify_current_phat, sha
import torch


def quaternion(x):
    t,y,z=x; c=np.cos(t/2);s=np.sin(t/2);w=np.sqrt(max(0.,1-y*y-z*z))
    return np.array([w*c,w*s,y*c+z*s,z*c-y*s])


def nearest(q, joint, thorough=False):
    lim=np.array(joint['limits_rad'])-1e-7
    axes=np.sin(lim[1:]/2)
    v=coords(q);v[0]=np.clip(v[0],-lim[0],lim[0])
    v[1:]/=max(1.,np.linalg.norm(v[1:]/axes))
    def objective(x):return 1-float(quaternion(x)@q)**2
    constraint={'type':'ineq','fun':lambda x:1-np.sum((x[1:]/axes)**2)}
    seeds=[v,np.zeros(3)]
    if thorough:
        seeds += [np.array([t,axes[0]*np.cos(a)*.95,axes[1]*np.sin(a)*.95])
                  for t in (-lim[0],0,lim[0]) for a in np.linspace(0,2*np.pi,12,endpoint=False)]
    results=[minimize(objective,s,method='SLSQP',bounds=[(-lim[0],lim[0]),(-axes[0],axes[0]),(-axes[1],axes[1])],
                      constraints=constraint,options={'ftol':1e-13,'maxiter':150}) for s in seeds]
    results=[r for r in results if r.success and constraint['fun'](r.x)>-1e-8]
    assert results,'Nearest rotation optimization failed'
    result=min(results,key=lambda r:r.fun)
    x=result.x.copy();x[1:]/=max(1.,np.linalg.norm(x[1:]/axes))
    p=quaternion(x)
    distance=2*np.arccos(np.clip(abs(p@q),0,1))
    return p,float(distance)


def poses(model,frames):
    p,q=model.forward_kinematics(torch.tensor(frames[:,:3],dtype=torch.float32),
        torch.tensor(R.from_rotvec(frames[:,3:6]).as_quat(),dtype=torch.float32),
        model.dof_to_rot(torch.tensor(frames[:,6:],dtype=torch.float32)))
    return np.concatenate((p.numpy(),q.numpy()),axis=-1)


def main():
    OUT.mkdir(exist_ok=True)
    asset=ROOT/'Saved/MimicKitCrawl/package/assets/uefn'
    meta=verify_current_phat(asset)
    source=ROOT/'Saved/MimicKitCrawl/package/motions/crawl.pkl'
    clip=pickle.loads(source.read_bytes());frames=clip['frames']
    model=MJCFCharModel('cpu');model.load(str(asset/'humanoid_uefn.xml'))
    torch.set_num_threads(1)
    cases=[];probe=[]
    for side in ('right','left'):
        joint=next(j for j in meta['joints'] if j['body']==side+'_upper_arm')
        _,qs=sampled_coordinates(model,joint,frames,1)
        candidates=[nearest(q,joint) for q in qs]
        index=int(np.argmax([c[1] for c in candidates]))
        q,distance=nearest(qs[index],joint,thorough=True)
        reference=R.from_quat(np.array(joint['reference_wxyz'])[[1,2,3,0]])
        delta=reference.inv()*R.from_quat(q[[1,2,3,0]])
        target=frames[index].copy();limited=target.copy()
        k=model.get_joint(model.get_body_names().index(joint['body']));start=6+k.dof_idx
        limited[start:start+3]=delta.as_rotvec()
        pair=poses(model,np.stack((target,limited)))
        # Global source heading/location are the same for both; centre on root XY.
        pair[:,:,:2]-=pair[0,0,:2].copy()
        actual_q=sampled_coordinates(model,joint,np.stack((limited,limited)),1)[1][0]
        probe.append([len(probe),*joint['modes'],*joint['limits_rad'],*actual_q])
        tv=coords(qs[index]);lv=coords(actual_q)
        deg=lambda v:np.rad2deg(np.r_[v[0],2*np.arcsin(np.clip(v[1:],-1,1))]).tolist()
        hand=model.get_body_names().index(side+'_hand')
        elbow=model.get_body_names().index(side+'_lower_arm')
        cases.append(dict(side=side,body=joint['body'],body_index=model.get_body_names().index(joint['body']),
            elbow_index=elbow,hand_index=hand,frame=index,fps=clip['fps'],seconds=index/clip['fps'],
            correction_deg=float(np.rad2deg(distance)),limits_deg=np.rad2deg(joint['limits_rad']).tolist(),
            target_angles_deg=deg(tv),limited_angles_deg=deg(lv),target=pair[0].round(7).tolist(),limited=pair[1].round(7).tolist(),
            hand_displacement_cm=float(np.linalg.norm(pair[1,hand,:3]-pair[0,hand,:3])*100),
            elbow_displacement_cm=float(np.linalg.norm(pair[1,elbow,:3]-pair[0,elbow,:3])*100)))
        print(side,'frame',index,'time',index/clip['fps'],'correction deg',np.rad2deg(distance),flush=True)
    np.savetxt(OUT/'jolt-input.csv',probe,delimiter=',',header='index,m0,m1,m2,a,b,c,w,x,y,z',comments='',fmt='%.12g')
    env=dict(os.environ);env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env['PATH']
    subprocess.run([str(ROOT/'Saved/Robotics/jolt_probe.exe'),'--limits',str(OUT/'jolt-input.csv'),str(OUT/'jolt-output.csv')],env=env,check=True,capture_output=True)
    check=np.genfromtxt(OUT/'jolt-output.csv',names=True,delimiter=',')
    assert np.all(check['mask']==0),check
    bodies=[]
    for body in ET.parse(asset/'humanoid_uefn.xml').findall('.//body'):
        shapes=[]
        for g in body.findall('geom'):
            shapes.append(dict(type=g.get('type'),size=list(map(float,g.get('size').split())),
                pos=list(map(float,g.get('pos','0 0 0').split())),quat=list(map(float,g.get('quat','1 0 0 0').split()))))
        bodies.append(dict(name=body.get('name'),shapes=shapes))
    assert [b['name'] for b in bodies]==model.get_body_names()
    doc=dict(clip='crawl',source=str(source),source_sha256=sha(source),limits_sha256=sha(asset/'limits.json'),
        method='Largest minimum quaternion angular correction across 433 cleaned crawl frames per upper arm. Constrained multistart optimization in current PHAT swing ellipse and twist bounds; selected results verified by project Jolt. Only selected shoulder local rotation changes; all other local joints held fixed. No ground-contact optimization.',
        bodies=bodies,cases=cases,jolt_verified=True)
    (OUT/'data.json').write_text(json.dumps(doc,indent=2))

if __name__=='__main__':main()
