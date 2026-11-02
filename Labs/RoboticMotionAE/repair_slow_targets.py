"""Offline, collision-aware repair of reduced slow-loco references.

Uses the training model's FK, compound PHAT geometry and exact joint limits.
Original Cutter/FBX/AE files are never overwritten.
"""
import json, pickle, sys, hashlib, argparse
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
import mujoco
import torch
from scipy.optimize import minimize
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Labs/LafanCutter'))
import retarget_crawls as rt
from motion import read_motion
from test_model import coords,violation

P=ROOT/'Saved/MimicKitSlowLoco/package'
OUT=ROOT/'Saved/MimicKitSlowLoco/retarget-repair-20261031'
def write(p,x):p.write_text(json.dumps(x,indent=2))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class Geometry:
    def __init__(self):
        torch.set_num_threads(1)
        self.meta=json.loads((P/'assets/uefn/limits.json').read_text())
        self.k=rt.MJCFCharModel('cpu');self.k.load(str(P/'assets/uefn/humanoid_uefn.xml'))
        self.names=self.k.get_body_names();self.parents=np.asarray(self.k._parent_indices)
        self.lp=self.k._local_translation.numpy().astype(float)
        self.lr=R.from_quat(self.k._local_rotation.numpy()).as_matrix()
        self.joints=[self.k.get_joint(i) for i in range(1,15)]
        self.gs=self.meta['geometry'];self.gb=np.array([self.names.index(g['body']) for g in self.gs])
        refs=self.meta['body_frames']
        self.gp=[];self.gr=[]
        xml=['<mujoco><worldbody>']
        for i,g in enumerate(self.gs):
            b=refs[g['body']];br=R.from_quat(b['quaternion']).as_matrix()
            self.gp.append(br.T@(np.array(g['position'])-b['position']))
            self.gr.append(br.T@R.from_quat(g['quaternion']).as_matrix())
            xml.append('<geom name="g%d" type="%s" size="%s"/>'%(i,g['type'],' '.join(map(str,g['size']))))
        xml.append('</worldbody></mujoco>')
        self.m=mujoco.MjModel.from_xml_string(''.join(xml));self.d=mujoco.MjData(self.m)
        self.gp=np.array(self.gp);self.gr=np.array(self.gr)
        excluded={tuple(sorted(x)) for x in self.meta['collision_exclusions']}
        self.pairs=[(a,b) for a in range(len(self.gs)) for b in range(a+1,len(self.gs))
                    if self.gb[a]!=self.gb[b] and tuple(sorted((self.gs[a]['body'],self.gs[b]['body']))) not in excluded]
        self.armleg=[(a,b) for a,b in self.pairs if
            ((3<=self.gb[a]<=8 and self.gb[b]>=9) or (3<=self.gb[b]<=8 and self.gb[a]>=9))]
    def fk(self,f):
        p=np.empty((15,3));r=np.empty((15,3,3));p[0]=f[:3];r[0]=R.from_rotvec(f[3:6]).as_matrix()
        for i,j in enumerate(self.joints,1):
            parent=self.parents[i];v=f[6+j.dof_idx:6+j.dof_idx+j.get_dof_dim()]
            delta=R.from_rotvec(v if len(v)==3 else j.axis.numpy().astype(float)*v[0]).as_matrix()
            p[i]=p[parent]+r[parent]@self.lp[i];r[i]=r[parent]@self.lr[i]@delta
        return p,r
    def set_pose(self,p,r):
        self.d.geom_xpos[:]=p[self.gb]+np.einsum('gij,gj->gi',r[self.gb],self.gp)
        self.d.geom_xmat[:]=(r[self.gb]@self.gr).reshape(-1,9)
    def distance(self,a,b):
        if self.gs[a]['type']==self.gs[b]['type']=='box':
            # Exact OBB overlap predicate via 15 separating axes. MuJoCo's
            # closest-distance query can return zero for near-parallel boxes
            # even when separated; this avoids an unstable contact gradient.
            ra=self.d.geom_xmat[a].reshape(3,3);rb=self.d.geom_xmat[b].reshape(3,3)
            axes=np.vstack((ra.T,rb.T,np.cross(ra.T[:,None,:],rb.T[None,:,:]).reshape(-1,3)))
            lengths=np.linalg.norm(axes,axis=1);axes=axes[lengths>1e-7]/lengths[lengths>1e-7,None]
            delta=self.d.geom_xpos[b]-self.d.geom_xpos[a]
            return float(np.max(abs(axes@delta)-abs(axes@ra)@self.gs[a]['size']-abs(axes@rb)@self.gs[b]['size']))
        return mujoco.mj_geomDistance(self.m,self.d,a,b,10.,None)
    def distances(self,f,pairs=None):
        p,r=self.fk(f);self.set_pose(p,r)
        return np.array([self.distance(a,b) for a,b in (pairs or self.pairs)])
    def limits(self,f):
        result={}
        for mj in self.meta['joints']:
            j=self.k.get_joint(self.names.index(mj['body']));v=f[6+j.dof_idx:6+j.dof_idx+j.get_dof_dim()]
            if len(v)==1:
                result[mj['body']]=not mj['range_rad'][0]-1e-6<=v[0]<=mj['range_rad'][1]+1e-6
            else:
                q=(R.from_quat(np.array(mj['reference_wxyz'])[[1,2,3,0]])*R.from_rotvec(v)).as_quat()[[3,0,1,2]]
                result[mj['body']]=bool(violation(coords(q),mj))
        return result
    def limit_margin(self,f):
        margins=[]
        for mj in self.meta['joints']:
            j=self.k.get_joint(self.names.index(mj['body']));v=f[6+j.dof_idx:6+j.dof_idx+j.get_dof_dim()]
            if len(v)==1:
                lo,hi=mj['range_rad'];margins.extend([v[0]-lo,hi-v[0]])
            else:
                q=(R.from_quat(np.array(mj['reference_wxyz'])[[1,2,3,0]])*R.from_rotvec(v)).as_quat()[[3,0,1,2]]
                c=coords(q);lim=mj['limits_rad'];assert mj['modes']==[1,1,1]
                margins.extend([lim[0]-c[0],lim[0]+c[0],1-(c[1]/np.sin(lim[1]/2))**2-(c[2]/np.sin(lim[2]/2))**2])
        return np.array(margins)
    def floors(self):
        values=[]
        for i,g in enumerate(self.gs):
            r=self.d.geom_xmat[i].reshape(3,3);z=self.d.geom_xpos[i,2];s=g['size']
            values.append(z-(np.abs(r[2])@s if g['type']=='box' else s[0]+abs(r[2,2])*s[1]))
        return np.array(values)
    def audit(self,frames):
        ds=np.array([self.distances(f) for f in frames]);ids=[self.pairs.index(x) for x in self.armleg]
        lim=[self.limits(f) for f in frames]
        worst=np.unravel_index(ds.argmin(),ds.shape);a,b=self.pairs[worst[1]]
        return dict(frames=len(frames),arm_leg_worst_penetration_cm=float(max(0,-ds[:,ids].min())*100),
            arm_leg_penetrating_frames=int((ds[:,ids].min(1)<-.001).sum()),
            worst_penetration_cm=float(max(0,-ds.min())*100),worst_pair=[self.gs[a]['name'],self.gs[b]['name']],worst_frame=int(worst[0]),
            limit_violations={n:sum(x[n] for x in lim) for n in lim[0] if any(x[n] for x in lim)},
            penetrations=[dict(pair=[self.gs[a]['name'],self.gs[b]['name']],max_cm=float(-ds[:,i].min()*100))
                          for i,(a,b) in enumerate(self.pairs) if ds[:,i].min()<-.001])

def source_wanted(g,name):
    manifest=json.loads((P/'prepared/manifest.json').read_text());item=next(x for x in manifest['motions'] if x['id']==name)
    conversion=Path(item['source']).with_name(Path(item['source']).name.replace('_robotic.pkl','_conversion.json'))
    motion=read_motion(Path(json.loads(conversion.read_text())['source']))
    rot=rt.source_rotations(motion);meta=g.meta
    rig=json.loads((ROOT/meta['source_rig']).read_text())
    reference={b['name']:rt.matrix(b['reference']['position_cm']+b['reference']['rotation_xyzw']) for b in rig['bodies']}
    asset=np.eye(4);asset[:3,:3]=rt.ASSET;wanted=[]
    for n in g.names:
        anchor=meta['groups'][n]['anchor'];j=motion.names.index(anchor)
        pose=np.tile(np.eye(4),(motion.count,1,1));pose[:,:3,:3]=rt.WORLD@rot[:,j]@np.diag([1.,-1.,1.])
        pose[:,:3,3]=motion.positions[:,j]@rt.WORLD.T
        offset=np.linalg.inv(reference[anchor])@np.linalg.inv(asset)@rt.serialized(meta['body_frames'][n])
        wanted.append(pose@offset)
    return np.stack(wanted,1)

def audit():
    OUT.mkdir(parents=True,exist_ok=True);g=Geometry();report={}
    for path in sorted((P/'motions').glob('*.pkl')):
        f=pickle.loads(path.read_bytes())['frames'];row=g.audit(f)
        wanted=source_wanted(g,path.stem)
        p=np.array([g.fk(x)[0] for x in f]);err=np.linalg.norm(p-wanted[:,:,:3,3],axis=-1)*100
        row['source_position_max_error_cm']=dict(zip(g.names,err.max(0).tolist()))
        # Distinguish original thick-collider overlap from reduction errors.
        sd=[]
        for x in wanted:
            g.set_pose(x[:,:3,3],x[:,:3,:3]);sd.append([g.distance(a,b) for a,b in g.armleg])
        row['source_arm_leg_worst_penetration_cm']=float(max(0,-np.min(sd))*100)
        report[path.stem]=row;print(path.stem,json.dumps(row),flush=True)
    write(OUT/'audit-before.json',report)

def repair_frame(g,original,wanted,previous=None,previous_original=None,maxiter=120,clearance=.004,joint_safety=.0001,rotation_weight=.08):
    """Hard joint/contact constraints; preserve the closest authored pose."""
    _,ref_r=g.fk(original);target_p=wanted[:,:3,3]
    ids=np.r_[2,np.arange(6,40)]
    bounds=[(float(original[2]-.05),float(original[2]+.3))]
    specs=[]
    for mj in g.meta['joints']:
        joint=g.k.get_joint(g.names.index(mj['body']));n=joint.get_dof_dim();idx=1+joint.dof_idx
        ref=R.from_quat(np.array(mj['reference_wxyz'])[[1,2,3,0]])
        specs.append((mj,n,idx,ref))
        bounds.extend([(-mj['limits_rad'][0]+max(1e-4,joint_safety*.1),mj['limits_rad'][0]-max(1e-4,joint_safety*.1)),(-1.,1.),(-1.,1.)] if n==3 else [(mj['range_rad'][0]+1e-4,mj['range_rad'][1]-1e-4)])
    def to_parameters(f):
        x=np.empty(35);x[0]=f[2]
        for mj,n,i,ref in specs:
            if n==1:x[i]=f[i+5]
            else:
                q=(ref*R.from_rotvec(f[i+5:i+8])).as_quat()[[3,0,1,2]];v=coords(q)
                x[i]=v[0];x[i+1:i+3]=v[1:]/np.sin(np.array(mj['limits_rad'][1:])/2)
                mag=np.linalg.norm(x[i+1:i+3])
                if mag>.9999:x[i+1:i+3]*=.9999/mag
        return np.clip(x,np.array(bounds)[:,0],np.array(bounds)[:,1])
    start=to_parameters(original if previous is None else previous)
    smooth=None
    if previous is not None:
        pp,pr=g.fk(previous);op,orr=g.fk(previous_original)
        smooth=(pp-op,pr@orr.transpose(0,2,1))
    orig_p,_=g.fk(original)
    def frame(x):
        f=original.astype(float).copy();f[2]=x[0]
        for mj,n,i,ref in specs:
            if n==1:f[i+5]=x[i]
            else:
                v=x[i+1:i+3]*np.sin(np.array(mj['limits_rad'][1:])/2)
                mag=np.linalg.norm(v)
                if mag>.999999:v*=.999999/mag
                s=np.sqrt(max(1e-12,1-v@v));c=np.cos(x[i]/2);sn=np.sin(x[i]/2);y,z=v
                q=np.array([s*sn,y*c+z*sn,z*c-y*sn,s*c])
                f[i+5:i+8]=(ref.inv()*R.from_quat(q)).as_rotvec()
        return f
    # Full geometry constraint prevents an arm fix from introducing torso,
    # opposite-limb or floor clipping. Exclusions match the real physics asset.
    near=[pair for pair,d in zip(g.pairs,g.distances(frame(start))) if d<.12]
    weights=np.ones(15);weights[[4,5,7,8]]=3;weights[[0,9,10,11,12,13,14]]=2
    last={}
    def calc(x):
        if 'x' in last and np.array_equal(x,last['x']):return last
        f=frame(x);p,r=g.fk(f);g.set_pose(p,r)
        dist=np.array([g.distance(a,b) for a,b in near])
        position=((p-target_p)**2*weights[:,None]).sum()*100
        # Matrix chord distance is smooth and independent of rotvec branch.
        rotation=((r-ref_r)**2).sum()*rotation_weight
        value=position+rotation+400*(f[2]-original[2])**2
        if smooth is not None:
            value+=5*((p-orig_p-smooth[0])**2).sum()+.15*((r@ref_r.transpose(0,2,1)-smooth[1])**2).sum()
        joint_constraints=[1.-joint_safety-(x[i+1:i+3]**2).sum() for mj,n,i,ref in specs if n==3]
        last.update(x=x.copy(),objective=value,constraints=np.r_[dist-clearance,g.floors()-.001,joint_constraints])
        return last
    result=None
    for _ in range(3):
        last.clear()
        result=minimize(lambda x:calc(x)['objective'],start,method='SLSQP',bounds=bounds,
            constraints=[dict(type='ineq',fun=lambda x:calc(x)['constraints'])],
            options=dict(maxiter=maxiter,ftol=1e-5,eps=2e-6))
        f=frame(result.x);all_d=g.distances(f)
        missing=[p for p,d in zip(g.pairs,all_d) if d<clearance-1e-5 and p not in near]
        if not missing:break
        near+=missing;start=result.x
    margin=float(calc(result.x)['constraints'].min())
    dists=g.distances(f);floor=g.floors().min();lim=g.limit_margin(f).min()
    # An exact final vertical lift removes optimizer floor-tolerance residue;
    # it cannot change joint coordinates or any self-collider separation.
    lift=max(0.,.001-float(floor));f[2]+=lift;floor+=lift
    return f,dict(success=bool(result.success),message=result.message,iterations=result.nit,objective=float(result.fun),min_margin=margin,
        actual_min_clearance=float(dists.min()),actual_floor_min=float(floor),actual_limit_margin=float(lim),final_floor_lift_m=lift)

def probe():
    OUT.mkdir(parents=True,exist_ok=True);g=Geometry();f=pickle.loads((P/'motions/sitting.pkl').read_bytes())['frames'];w=source_wanted(g,'sitting')
    t=time.time();fixed,result=repair_frame(g,f[0],w[0]);print('seconds',time.time()-t,result,flush=True)
    np.savez(OUT/'probe.npz',before=f[0],after=fixed,wanted=w[0])
    print(json.dumps(g.audit(fixed[None]),indent=2))

def repair_clip(name):
    import os
    os.environ['OMP_NUM_THREADS']='1'
    g=Geometry();source=P/'motions'/f'{name}.pkl';data=pickle.loads(source.read_bytes());frames=data['frames'];wanted=source_wanted(g,name)
    fixed=[];receipts=[];started=time.time()
    partial=OUT/(name+'-partial.npz')
    if partial.exists():
        saved=np.load(partial);np.testing.assert_array_equal(saved['before'],frames[:len(saved['before'])])
        fixed=list(saved['after']);receipts=[dict(reused_validated_partial=True) for _ in fixed]
        for f in fixed:
            assert g.distances(f).min()>0 and not any(g.limits(f).values())
    for i in range(len(fixed),len(frames)):
        f,w=frames[i],wanted[i]
        new,result=repair_frame(g,f,w,fixed[-1] if fixed else None,frames[i-1] if fixed else None,maxiter=50 if fixed else 150)
        def admissible(result):
            return result['actual_min_clearance']>=.00001 and result['actual_floor_min']>=0 and result['actual_limit_margin']>=0
        if not admissible(result):
            new,result=repair_frame(g,f,w,new,f,maxiter=150)
        if not admissible(result):
            np.savez(OUT/(name+'-failed.npz'),before=f,after=new,wanted=w)
            raise RuntimeError((name,i,result))
        fixed.append(new);receipts.append(result)
        np.savez(OUT/(name+'-partial.npz'),before=frames[:len(fixed)],after=np.array(fixed),wanted=wanted[:len(fixed)])
        if i%10==0:print(name,i,len(frames),round(time.time()-started,1),flush=True)
    corrected=np.array(fixed,dtype=np.float32)
    for j in g.joints:
        if j.get_dof_dim()==3:
            sl=slice(6+j.dof_idx,9+j.dof_idx);corrected[:,sl]=R.from_rotvec(corrected[:,sl]).as_rotvec()
    path=OUT/'candidates'/f'{name}.pkl';path.parent.mkdir(exist_ok=True)
    path.write_bytes(pickle.dumps(dict(data,frames=corrected)))
    np.savez_compressed(OUT/'candidates'/f'{name}.npz',before=frames,after=corrected,wanted=wanted)
    report=dict(source_sha256=sha(source),candidate_sha256=sha(path),seconds=time.time()-started,
                before=g.audit(frames),after=g.audit(corrected),optimizer=receipts)
    write(OUT/'candidates'/f'{name}.json',report)
    print('DONE',name,round(report['seconds'],1),report['after'],flush=True)
    return name

def repair():
    from concurrent.futures import ProcessPoolExecutor,as_completed
    OUT.mkdir(parents=True,exist_ok=True)
    with ProcessPoolExecutor(max_workers=4) as pool:
        paths=sorted((P/'motions').glob('*.pkl'),key=lambda p:(p.stem!='sitting',p.stem))
        paths=[p for p in paths if not (OUT/'candidates'/p.name).exists()]
        jobs=[pool.submit(repair_clip,p.stem) for p in paths]
        for f in as_completed(jobs):
            try:print('COMPLETED',f.result(),flush=True)
            except Exception as e:print('FAILED',repr(e),flush=True)

def apply():
    import shutil
    validation=json.loads((OUT/'validation.json').read_text());assert validation['passed'] and len(validation['motions'])==8
    backup=OUT/'before';backup.mkdir(exist_ok=False);(backup/'motions').mkdir()
    manifest_path=P/'prepared/manifest.json';shutil.copy2(manifest_path,backup/'manifest.json')
    manifest=json.loads(manifest_path.read_text());accepted=[]
    for row in manifest['motions']:
        name=row['id'];source=P/'motions'/f'{name}.pkl';candidate=OUT/'candidates'/source.name
        report=next(x for x in validation['motions'] if x['clip']==name)
        assert sha(candidate)==report['sha256'] and report['passed']
        assert sha(Path(row['source']))==row['source_sha256'],'Original export changed'
        shutil.copy2(source,backup/'motions'/source.name);shutil.copy2(candidate,source)
        row['training_sha256']=sha(source)
        row['retarget_repair']=dict(method='Collision-aware PHAT-constrained offline reference fitting; coherent idle correction; dense interpolation checks',
            receipt='prepared/retarget-repair.json',original_training_sha256=sha(backup/'motions'/source.name))
        accepted.append(dict(id=name,file=str(source),sha256=sha(source),original_sha256=sha(backup/'motions'/source.name)))
    write(manifest_path,manifest)
    local=P.parent/'prepared/manifest.json'
    local.write_text(manifest_path.read_text().replace('/workspace/mimickit_trial',P.resolve().as_posix()))
    receipt=dict(applied=True,validation=validation,motions=accepted,originals_preserved=str(backup),
        geometry_joint_limits_and_policy_settings_unchanged=True,algorithm_sha256=sha(Path(__file__)))
    write(OUT/'accepted.json',receipt);write(P/'prepared/retarget-repair.json',receipt)
    print('Applied eight validated references; originals preserved',flush=True)

if __name__=='__main__':globals()[sys.argv[1] if len(sys.argv)>1 else 'audit']()
