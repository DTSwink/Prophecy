"""Offline CPU-only PHAT-valid dead-limb initial states; active pose stays exact."""
import os
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
import json,pickle,time,hashlib
import numpy as np
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry,P,ROOT
from disabled_limb_rules import valid_codes,limb_bodies

OUT=ROOT/'Saved/MimicKitSlowLoco/disabled-curriculum-deploy-20261102'
SAMPLES=64

def generate():
    g=Geometry(); rng=np.random.default_rng(20261102)
    names=[x['id'] for x in json.loads((P/'prepared/manifest.json').read_text())['motions']]
    dofs=[]; bodies=[]; joint_meta={x['body']:x for x in g.meta['joints']}
    for limb in range(4):
        bs=[g.names.index(b) for b in limb_bodies(limb)]; bodies.append(bs)
        dofs.append(np.concatenate([np.arange(g.k.get_joint(b).dof_idx,g.k.get_joint(b).dof_idx+g.k.get_joint(b).get_dof_dim()) for b in bs]))
    def random_limb(limb):
        values=[]
        for body in limb_bodies(limb):
            mj=joint_meta[body]
            if 'range_rad' in mj:
                values.append([rng.uniform(*mj['range_rad'])]);continue
            lim=np.array(mj['limits_rad'])*.995
            twist=rng.uniform(-lim[0],lim[0]); a=rng.uniform(0,2*np.pi);r=np.sqrt(rng.random())
            y=r*np.cos(a)*np.sin(lim[1]/2);z=r*np.sin(a)*np.sin(lim[2]/2);w=np.sqrt(1-y*y-z*z)
            c,s=np.cos(twist/2),np.sin(twist/2)
            q=R.from_quat([w*s,y*c+z*s,z*c-y*s,w*c])
            ref=R.from_quat(np.array(mj['reference_wxyz'])[[1,2,3,0]])
            values.append((ref.inv()*q).as_rotvec())
        return np.concatenate(values)
    states=np.zeros((10,16,SAMPLES,34),np.float32);times=np.zeros((10,16,SAMPLES),np.float32)
    report={};start=time.time()
    for mi,name in enumerate(names):
        clip=pickle.load(open(P/'motions'/f'{name}.pkl','rb')); frames=clip['frames'];fps=clip['fps']
        codes=sorted({c for n in (1,2,3) for c in valid_codes(name,n)})
        for code in codes:
            records=[];attempts=0
            for sample in range(SAMPLES):
                fi=int((sample+.5)*(len(frames)-1)/SAMPLES)
                base=frames[fi].astype(float);f=base.copy()
                dead=[l for l in range(4) if code&(1<<l)]
                # Randomise one chain at a time; filter only collision pairs
                # touched by it. Never lift/rotate pelvis or move an enabled chain.
                for retry in range(12):
                    f=base.copy()
                    for limb in rng.permutation(dead):
                        bs=bodies[limb]; ds=dofs[limb]; geoms=np.isin(g.gb,bs)
                        pairs=[p for p in g.pairs if geoms[p[0]] or geoms[p[1]]]
                        found=False
                        for trial in range(600):
                            attempts+=1; candidate=f.copy();v=random_limb(limb)
                            # Confined support poses get a smaller, still random
                            # perturbation if full-range samples cannot fit.
                            blend=1. if trial<120 else .35 if trial<300 else .12
                            for b in bs:
                                j=g.k.get_joint(b); ix=np.arange(j.dof_idx,j.dof_idx+j.get_dof_dim());loc=np.searchsorted(ds,ix)
                                orig=base[6+ix];target=v[loc]
                                if len(ix)==1: candidate[6+ix]=orig+blend*(target-orig)
                                else:
                                    q=R.from_rotvec(orig);candidate[6+ix]=(q*R.from_rotvec((q.inv()*R.from_rotvec(target)).as_rotvec()*blend)).as_rotvec()
                            if np.linalg.norm(candidate[6+ds]-base[6+ds])<.08:continue
                            p,r=g.fk(candidate);g.set_pose(p,r)
                            if g.floors()[geoms].min() < 0.0001:continue
                            if any(g.distance(a,b)<-.0001 for a,b in pairs):continue
                            if any(g.limits(candidate)[g.names[b]] for b in bs):continue
                            f=candidate;found=True;break
                        if not found:break
                    if found:break
                if not found:raise RuntimeError((name,code,sample,limb,'no valid random init after backtracking'))
                changed=np.concatenate([dofs[l] for l in dead]);unchanged=np.setdiff1d(np.arange(34),changed)
                assert np.array_equal(f[:6],base[:6]) and np.array_equal(f[6+unchanged],base[6+unchanged])
                # Validate final float32 state, not just the solver's float64.
                f=f.astype(np.float32);p,r=g.fk(f);g.set_pose(p,r)
                geoms=np.isin(g.gb,np.concatenate([bodies[l] for l in dead]))
                floor=float(g.floors()[geoms].min());overlap=min(g.distance(a,b) for a,b in g.pairs if geoms[a] or geoms[b])
                assert floor>=0 and overlap>=-.0002 and not any(g.limits(f)[g.names[b]] for l in dead for b in bodies[l])
                states[mi,code,sample]=f[6:];times[mi,code,sample]=fi/fps
                records.append((floor,overlap,float(np.linalg.norm(f[6+changed]-base[6+changed]))))
            report[f'{name}:{code}']=dict(samples=SAMPLES,attempts=attempts,min_floor_m=min(x[0] for x in records),
                max_overlap_m=max(0,-min(x[1] for x in records)),min_joint_change_rad=min(x[2] for x in records))
            print(name,code,'complete',round(time.time()-start,1),flush=True)
    dest=OUT/'disabled_inits.npz';np.savez_compressed(dest,dof_pos=states,times=times)
    result=dict(passed=True,seed=20261102,samples_per_mask=SAMPLES,groups=report,
        source_motion_sha256={n:hashlib.sha256((P/'motions'/f'{n}.pkl').read_bytes()).hexdigest() for n in names},
        limits_sha256=hashlib.sha256((P/'assets/uefn/limits.json').read_bytes()).hexdigest(),
        bank_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),seconds=time.time()-start)
    (OUT/'init-report.json').write_text(json.dumps(result,indent=2))
if __name__=='__main__':generate()
