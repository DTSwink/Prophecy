"""Review-only IK candidates: fixed hand transforms, explicit PHAT constraints."""
import argparse, json, pickle, sys, time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R, Slerp
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Labs/MimicKitUEFN'))
from fit_motion_limits import MJCFCharModel, sampled_coordinates
from test_model import coords, violation
from current_phat import verify_current_phat, sha


class ContactIK:
    def __init__(self,model,meta):
        self.model=model;self.meta=meta;self.names=model.get_body_names()
        self.lp=model._local_translation.numpy().astype(float)
        self.lr=R.from_quat(model._local_rotation.numpy()).as_matrix()
        self.parents=np.asarray(model._parent_indices)
        self.joints={j['body']:j for j in meta['joints']}
        self.ids={name:i for i,name in enumerate(self.names)}
        self.slices={}
        for i,name in enumerate(self.names[1:],1):
            k=model.get_joint(i);self.slices[name]=slice(6+k.dof_idx,6+k.dof_idx+k.get_dof_dim())
        self.selected=['torso','right_upper_arm','right_lower_arm','left_upper_arm','left_lower_arm']
        self.indices=np.concatenate([np.arange(self.slices[n].start,self.slices[n].stop) for n in self.selected])
        self.handids=[self.ids[n] for n in ('right_hand','left_hand')]
        self.ref={n:R.from_quat(np.array(j['reference_wxyz'])[[1,2,3,0]]) for n,j in self.joints.items()}

    def fk(self,f):
        p=np.zeros((15,3));r=np.zeros((15,3,3));p[0]=f[:3];r[0]=R.from_rotvec(f[3:6]).as_matrix()
        for i,name in enumerate(self.names[1:],1):
            d=f[self.slices[name]];q=R.from_rotvec(d if len(d)==3 else np.array([0,0,d[0]])).as_matrix()
            parent=self.parents[i];p[i]=p[parent]+r[parent]@self.lp[i];r[i]=r[parent]@self.lr[i]@q
        return p,r

    def margins(self,f,names,margin_deg=.25):
        result=[]
        for name in names:
            j=self.joints[name];d=f[self.slices[name]]
            if j['kind']=='hinge':
                result.extend([d[0]-j['range_rad'][0]-np.deg2rad(margin_deg),j['range_rad'][1]-np.deg2rad(margin_deg)-d[0]])
            else:
                q=(self.ref[name]*R.from_rotvec(d)).as_quat()[[3,0,1,2]];v=coords(q)
                lim=np.array(j['limits_rad'])-np.deg2rad(margin_deg)
                result.extend([lim[0]-v[0],lim[0]+v[0],1-np.sum((v[1:]/np.sin(lim[1:]/2))**2)])
        return np.array(result)

    def solve(self,base,original,initial=None,torso_limits=False,previous_delta=None,maxiter=160,smooth_weight=.3,hand_xy_tolerance=0.):
        target_p,target_r=self.fk(base)
        constrained=['right_upper_arm','left_upper_arm','right_lower_arm','left_lower_arm','right_hand','left_hand']
        if torso_limits:constrained+=['torso','head']
        ref_r={n:R.from_rotvec(original[self.slices[n]]) for n in self.selected if self.joints[n]['kind']=='ball'}
        weights={'torso':2.,'right_upper_arm':6.,'left_upper_arm':6.,'right_lower_arm':1.,'left_lower_arm':1.,'head':1.}
        cache={}
        def evaluate(x):
            key=x.tobytes()
            if key in cache:return cache[key]
            f=base.copy();f[self.indices]=x
            p,r=self.fk(f)
            for name in ('head','right_hand','left_hand'):
                if name in self.selected:continue
                i=self.ids[name];f[self.slices[name]]=R.from_matrix(self.lr[i].T@r[self.parents[i]].T@target_r[i]).as_rotvec()
            objective=0.
            for n in self.selected:
                d=f[self.slices[n]];o=original[self.slices[n]]
                if len(d)==3:diff=(ref_r[n].inv()*R.from_rotvec(d)).as_rotvec()
                else:diff=d-o
                objective+=weights[n]*float(diff@diff)
            # Prefer the same smooth correction across neighboring source poses.
            if previous_delta is not None:
                diff=x-original[self.indices]-previous_delta;objective+=smooth_weight*float(diff@diff)
            if hand_xy_tolerance:
                objective+=1e6*float(np.square(p[self.handids,:2]-target_p[self.handids,:2]).sum())
            val=(objective,(p[self.handids]-target_p[self.handids]).ravel(),self.margins(f,constrained),f)
            if len(cache)>100:cache.clear()
            cache[key]=val;return val
        seeds=[base[self.indices] if initial is None else initial[self.indices]]
        result=None
        for seed in seeds:
            seed=np.array(seed,dtype=float)
            constraints=[{'type':'eq','fun':lambda x:evaluate(x)[1]}, {'type':'ineq','fun':lambda x:evaluate(x)[2]}]
            if hand_xy_tolerance:
                constraints=[{'type':'eq','fun':lambda x:evaluate(x)[1].reshape(2,3)[:,2]},
                    {'type':'ineq','fun':lambda x:1-np.sum(evaluate(x)[1].reshape(2,3)[:,:2]**2,axis=1)/hand_xy_tolerance**2},
                    {'type':'ineq','fun':lambda x:evaluate(x)[2]}]
            r=minimize(lambda x:evaluate(x)[0],seed,method='SLSQP',constraints=constraints,
                options={'ftol':1e-10,'maxiter':maxiter})
            obj,error,margin,f=evaluate(r.x)
            result=(f,dict(success=bool(r.success),message=r.message,iterations=r.nit,
                position_error_m=float(np.max(np.abs(error))),height_error_m=float(abs(error.reshape(2,3)[:,2]).max()),minimum_margin=float(margin.min()),objective=obj))
        return result


def load():
    asset=ROOT/'Saved/MimicKitCrawl/package/assets/uefn';meta=verify_current_phat(asset)
    model=MJCFCharModel('cpu');model.load(str(asset/'humanoid_uefn.xml'))
    motion=pickle.loads((ROOT/'Saved/MimicKitCrawl/package/motions/crawl.pkl').read_bytes())
    old=motion['frames'].astype(float)
    raw=pickle.loads((ROOT/'Saved/RoboticCrawlAE/runs/20261017_053724_crawl_idle_2x512/data/03_crawl_robotic.pkl').read_bytes())['frames']
    # Recreate only the accepted source loop closure, never its contact IK.
    import repair_references as rr
    raw,_=rr.close_crawl_cycle(model,raw)
    times=np.arange(len(raw));query=np.linspace(0,len(raw)-1,len(old))
    original=np.stack([np.interp(query,times,raw[:,i]) for i in range(raw.shape[1])],-1)
    for j in meta['joints']:
        if j['kind']=='ball':
            k=model.get_joint(model.get_body_names().index(j['body']));start=6+k.dof_idx
            original[:,start:start+3]=Slerp(times,R.from_rotvec(raw[:,start:start+3]))(query).as_rotvec()
    original[:,:6]=old[:,:6]
    return ContactIK(model,meta),motion,old,original


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--probe',action='store_true');args=parser.parse_args()
    ik,motion,old,original=load()
    out=ROOT/'Saved/MimicKitCrawl/constrained-ik';out.mkdir(exist_ok=True)
    if args.probe:
        results=[]
        for i in (280,80,0,160,360):
            for torso in (False,True):
                start=time.time();f,report=ik.solve(old[i],original[i],torso_limits=torso,maxiter=100)
                report.update(frame=i,torso_limits=torso,seconds=time.time()-start)
                print(json.dumps(report),flush=True);results.append(report)
        (out/'probe.json').write_text(json.dumps(results,indent=2));return
    output=[];reports=[];initial=None;delta=None
    for i in range(len(old)-1):
        f,report=ik.solve(old[i],original[i],initial=initial,previous_delta=delta,smooth_weight=20.)
        if report['position_error_m']>1e-6 or report['minimum_margin']< -1e-7:
            raise RuntimeError((i,report))
        output.append(f);reports.append(report);initial=f
        delta=f[ik.indices]-original[i,ik.indices]
        if i%24==0:print(i,report,flush=True)
    f=output[0].copy();f[:6]=old[-1,:6]
    # Preserve the original leg cycle endpoint exactly.
    for n in ik.names:
        if any(s in n for s in ('thigh','shin','foot')):f[ik.slices[n]]=old[-1,ik.slices[n]]
    output.append(f)
    candidate=np.array(output,dtype=np.float32)
    np.testing.assert_array_equal(candidate[:,:6],old[:,:6].astype(np.float32))
    motion['frames']=candidate
    (out/'crawl.pkl').write_bytes(pickle.dumps(motion))
    (out/'solve.json').write_text(json.dumps(reports,indent=2))
    print('Saved candidate',out/'crawl.pkl',flush=True)

if __name__=='__main__':main()
