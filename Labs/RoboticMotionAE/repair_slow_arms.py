"""Arm-only contact IK. Never optimize root, trunk, head or either leg.

Sitting contacts retain their authored location in the corresponding leg frame.
The source wrist/hand orientation defines the target; PHAT thickness is accounted
for by bringing the hand box to the leg surface rather than embedding it.
"""
import argparse, json, pickle, time
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry, OUT as OLD, ROOT, write, sha, coords

OUT=ROOT/'Saved/MimicKitSlowLoco/arm-ik-20261031'
ARM_BODIES=tuple(range(3,9))

def indices(g):
    return np.concatenate([np.arange(6+g.k.get_joint(b).dof_idx,
        6+g.k.get_joint(b).dof_idx+g.k.get_joint(b).get_dof_dim()) for b in ARM_BODIES])

def targets(g, original, wanted):
    p,r=g.fk(original)
    g.set_pose(wanted[:,:3,3],wanted[:,:3,:3])
    source_p=g.d.geom_xpos.copy();source_r=g.d.geom_xmat.reshape(-1,3,3).copy()
    g.set_pose(p,r);robot_p=g.d.geom_xpos.copy();robot_r=g.d.geom_xmat.reshape(-1,3,3).copy()
    result=[]
    # Right hand rests by right knee; left hand is on the raised left shin.
    for hand,leg,hg,lg in [(5,9,13,17),(8,13,16,21)]:
        rel=wanted[leg,:3,:3].T@(wanted[hand,:3,3]-wanted[leg,:3,3])
        wrist=p[leg]+r[leg]@rel
        hr=r[leg]@wanted[leg,:3,:3].T@wanted[hand,:3,:3]
        # Authored contact longitude/latitude in the leg collider frame.
        hc=source_r[lg].T@(source_p[hg]-source_p[lg])
        radius,half=g.gs[lg]['size']
        axis=np.array([0.,0.,np.clip(hc[2],-half,half)])
        normal=hc-axis;normal/=np.linalg.norm(normal)
        nw=robot_r[lg]@normal
        hand_geom_r=hr@g.gr[hg]
        support=np.abs(hand_geom_r.T@nw)@g.gs[hg]['size']
        surface=robot_p[lg]+robot_r[lg]@(axis+radius*normal)
        hand_center=surface+nw*(support+.003)
        surface_wrist=hand_center-hr@g.gp[hg]
        result.append(dict(hand=hand,leg=leg,hg=hg,lg=lg,wrist=wrist,
            surface_wrist=surface_wrist,rotation=hr,surface=surface,normal=nw,leg_local_center=hc))
    return result

def solve(g, original, wanted, previous=None, previous_original=None, start_override=None, enforce_limits=True):
    ids=indices(g);before_p,before_r=g.fk(original);tar=targets(g,original,wanted)
    arm_pairs=[pair for pair in g.pairs if any(g.gb[i] in ARM_BODIES for i in pair)]
    arm_geoms=[i for i,b in enumerate(g.gb) if b in ARM_BODIES]
    specs=[m for m in g.meta['joints'] if g.names.index(m['body']) in ARM_BODIES]
    bounds=[(-7.,7.) for _ in ids]
    for mj in specs:
        j=g.k.get_joint(g.names.index(mj['body']))
        if j.get_dof_dim()==1:bounds[list(ids).index(6+j.dof_idx)]=tuple(mj['range_rad'])
    def frame(x):
        f=original.astype(float).copy();f[ids]=x;return f
    cache={}
    def calc(x):
        if 'x' in cache and np.array_equal(x,cache['x']):return cache
        f=frame(x);p,r=g.fk(f);g.set_pose(p,r)
        distances=np.array([g.distance(a,b) for a,b in arm_pairs])
        margins=[]
        for mj in specs:
            j=g.k.get_joint(g.names.index(mj['body']));v=f[6+j.dof_idx:6+j.dof_idx+j.get_dof_dim()]
            if len(v)==3:
                ref=R.from_quat(np.array(mj['reference_wxyz'])[[1,2,3,0]])
                q=(ref*R.from_rotvec(v)).as_quat()[[3,0,1,2]];c=coords(q);lim=mj['limits_rad']
                margins.extend([lim[0]-c[0],lim[0]+c[0],1.-(c[1]/np.sin(lim[1]/2))**2-(c[2]/np.sin(lim[2]/2))**2])
        value=0.
        for t in tar:
            h=t['hand'];elbow=h-1
            value+=150*np.sum((p[h]-t['wrist'])**2)
            local_center=g.d.geom_xmat[t['lg']].reshape(3,3).T@(g.d.geom_xpos[t['hg']]-g.d.geom_xpos[t['lg']])
            value+=15000*(local_center[2]-t['leg_local_center'][2])**2
            value+=.7*np.sum((r[h]-t['rotation'])**2)
            # Weak pole preference: retain the authored arm direction where reachable.
            value+=5*np.sum((p[elbow]-wanted[elbow,:3,3])**2)
            # Keep actual hand in contact with the authored leg, not floating beside it.
            value+=15000*max(0.,g.distance(t['hg'],t['lg'])-.004)**2
        value+=.03*np.sum((r[list(ARM_BODIES)]-before_r[list(ARM_BODIES)])**2)
        if previous is not None:
            pp,pr=g.fk(previous);op,orr=g.fk(previous_original)
            value+=2*np.sum((p[list(ARM_BODIES)]-before_p[list(ARM_BODIES)]-pp[list(ARM_BODIES)]+op[list(ARM_BODIES)])**2)
            value+=.02*np.sum((r[list(ARM_BODIES)]@before_r[list(ARM_BODIES)].transpose(0,2,1)-pr[list(ARM_BODIES)]@orr[list(ARM_BODIES)].transpose(0,2,1))**2)
        cache.update(x=x.copy(),value=value,margin=np.r_[distances-.002,g.floors()[arm_geoms]-.001,margins if enforce_limits else []])
        return cache
    start=original[ids].astype(float) if previous is None else previous[ids].copy()
    if start_override is not None:start=start_override
    result=minimize(lambda x:calc(x)['value'],start,method='SLSQP',bounds=bounds,
        constraints=[dict(type='ineq',fun=lambda x:calc(x)['margin'])],
        options=dict(maxiter=150,ftol=1e-7,eps=1e-6))
    f=frame(result.x).astype(original.dtype)
    untouched=np.setdiff1d(np.arange(len(original)),ids)
    assert np.array_equal(f[untouched],original[untouched])
    p,r=g.fk(f)
    report=dict(success=bool(result.success),message=result.message,nit=result.nit,objective=float(result.fun),
        min_margin=float(calc(f[ids])['margin'].min()),
        hands=[dict(hand=g.names[t['hand']],leg=g.names[t['leg']],
            surface_target_error_cm=float(np.linalg.norm(p[t['hand']]-t['surface_wrist'])*100),
            authored_wrist_error_cm=float(np.linalg.norm(p[t['hand']]-t['wrist'])*100),
            contact_distance_cm=float(g.distances(f,[(t['hg'],t['lg'])])[0]*100)) for t in tar])
    return f,report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',action='store_true');a=ap.parse_args()
    OUT.mkdir(exist_ok=True,parents=True);g=Geometry()
    original=pickle.loads((OLD/'before/motions/sitting.pkl').read_bytes())
    wanted=np.load(OLD/'candidates/sitting.npz')['wanted'];before=original['frames']
    if a.probe:
        rng=np.random.default_rng(128);best=None
        for n in range(8):
            start=None if n==0 else before[20,indices(g)]+rng.normal(0,.65,14)
            f,report=solve(g,before[20],wanted[20],start_override=start)
            print(n,report,flush=True)
            if report['min_margin']>-.0001 and (best is None or report['objective']<best[1]['objective']):best=f,report
        assert best is not None
        f,report=best;write(OUT/'probe.json',report)
        np.savez(OUT/'probe.npz',before=before[20],after=f,wanted=wanted[20]);print(json.dumps(report));return
    after=[];reports=[];started=time.time();seed=np.load(OUT/'probe.npz')['after'][indices(g)]
    for i,f in enumerate(before):
        new,report=solve(g,f,wanted[i],after[-1] if after else None,before[i-1] if after else None,
            start_override=seed+f[indices(g)]-before[20,indices(g)] if not after else None)
        after.append(new);reports.append(report)
        print(i,report['success'],report['min_margin'],flush=True)
    after=np.asarray(after);original['frames']=after
    (OUT/'sitting.pkl').write_bytes(pickle.dumps(original));np.savez(OUT/'sitting.npz',before=before,after=after,wanted=wanted)
    write(OUT/'solve.json',dict(seconds=time.time()-started,frames=reports,sha256=sha(OUT/'sitting.pkl')))

if __name__=='__main__':main()
