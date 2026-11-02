"""Bake uniform authored-to-perturbed+ starts; restart from original checkpoint."""
import hashlib,json,io,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import torch,yaml
import deploy_locomotion_branch as d
from precompute_loco_final_inits import SRC
from prepare_perturbed_com2 import MJCFCharModel,MotionLib,mp_util,q
from ground_random_phat_poses import floor_heights

def main():
    out=d.OUT/'final-phase-blended';out.mkdir(exist_ok=True)
    original=out/'original-plan.json'
    if not original.exists():original.write_bytes((d.OUT/'final-phase-prepared.json').read_bytes())
    plan=json.loads(original.read_text())
    with zipfile.ZipFile(plan['source']['local']) as z:entries={n:z.read(n) for n in z.namelist()}
    with np.load(io.BytesIO(entries['prepared/final_initializations.npz']),allow_pickle=False) as z:bank={k:z[k].copy() for k in z.files}
    torch.set_num_threads(1);mp_util.init(0,1,'cpu',2026102350)
    cfg=yaml.safe_load(entries['prepared/env_config.yaml'])
    local=yaml.safe_load(entries['prepared/env_config.yaml'].decode().replace('/workspace/mimickit_trial',SRC.as_posix()))
    model=MJCFCharModel('cpu');model.load(local['char_file'])
    motions=out/'motions.yaml';motions.write_text(entries['prepared/motions.yaml'].decode().replace('/workspace/mimickit_trial',SRC.as_posix()))
    lib=MotionLib(str(motions),model,'cpu');names=model.get_body_names();tree=ET.parse(local['char_file'])
    bodies=[]
    for name in names:
        body=tree.find(f".//body[@name='{name}']")
        bodies.append(dict(name=name,shapes=[dict(type=g.get('type','sphere'),size=list(map(float,g.get('size').split())),pos=list(map(float,g.get('pos','0 0 0').split())),quat=np.roll(list(map(float,g.get('quat','1 0 0 0').split())),-1).tolist()) for g in body.findall('geom')]))
    com=torch.tensor(list(map(float,tree.find(f".//body[@name='{names[0]}']/inertial").get('pos','0 0 0').split())))
    rng=np.random.default_rng(2026102350);count=1024;result={};max_floor_lift=0.;min_clearance=100.
    for motion in range(lib.get_num_motions()):
        times=torch.tensor(rng.uniform(0,float(lib.get_motion_length(motion)),count),dtype=torch.float32)
        rp,rq,rv,rw,jr,jv=lib.calc_motion_frame(torch.full((count,),motion),times)
        index=rng.integers(len(bank['plus_dof']),size=count);alpha=torch.tensor(rng.uniform(0,1,count),dtype=torch.float32)
        noise={k[5:]:torch.tensor(v[index]) for k,v in bank.items() if k.startswith('plus_')}
        nr=noise['root_pos'].float().clone();nr[:,:2]=rp[:,:2]
        root=torch.lerp(rp,nr,alpha[:,None]);rot=q.slerp(rq,noise['root_rot'].float(),alpha)
        nj=model.dof_to_rot(noise['dof'].float());joints=q.slerp(jr,nj,alpha[:,None].expand(jr.shape[:-1]))
        dof=lib.joint_rot_to_dof(joints);velocity=torch.lerp(jv,noise['dof_vel'].float(),alpha[:,None])
        # Intermediate rotations can penetrate even when both endpoints clear.
        p,r=model.forward_kinematics(root,rot,joints)
        lowest=floor_heights(torch.cat((p,r),-1).numpy(),bodies).min(1)
        lift=np.maximum(2e-6-lowest,0).astype(np.float32);root[:,2]+=torch.tensor(lift)
        max_floor_lift=max(max_floor_lift,float(lift.max()));min_clearance=min(min_clearance,float((lowest+lift).min()))
        omega=noise['root_ang'].float()
        # Preserve the sampled root-origin velocity; update COM offset convention.
        rootv=noise['root_vel'].float()+torch.cross(omega,q.quat_rotate(rot,com.expand(count,3))-q.quat_rotate(noise['root_rot'].float(),com.expand(count,3)),dim=-1)
        values=dict(root_pos=root,root_rot=rot,dof=dof,root_vel=rootv,root_ang=omega,dof_vel=velocity,
                    motion_time=times,blend=alpha,noise_index=torch.tensor(index),joint_frame=noise['joint_frame'],
                    root_frame=noise['root_frame'],floor_lift=torch.tensor(lift))
        for k,v in values.items():result.setdefault('plus_'+k,[]).append(v.numpy())
        # Explicit endpoint and interpolation checks, independent of physics.
        torch.testing.assert_close(torch.lerp(jv,noise['dof_vel'].float(),torch.zeros(count,1)),jv)
        torch.testing.assert_close(torch.lerp(jv,noise['dof_vel'].float(),torch.ones(count,1)),noise['dof_vel'].float())
        assert torch.isfinite(root).all() and torch.isfinite(dof).all()
    new={k:v for k,v in bank.items() if not k.startswith('plus_')}
    new.update({k:np.stack(v) for k,v in result.items()})
    path=out/'initializations.npz';np.savez_compressed(path,**new);sha=hashlib.sha256(path.read_bytes()).hexdigest()
    phase=cfg['perturbed_motion']['final_phase'];phase.update(sha256=sha,plus_blended=True,plus_foot_grace=50)
    entries['prepared/env_config.yaml']=yaml.safe_dump(cfg,sort_keys=False).encode()
    entries['prepared/final_initializations.npz']=path.read_bytes()
    entries['pipeline/final_locomotion.py']=Path(__file__).with_name('final_locomotion.py').read_bytes()
    archive=out/'source.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for k,v in entries.items():z.writestr(k,v)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    plan.update(source=dict(local=str(archive),key='mimickit/pipeline_20261014/final-locomotion/source_'+digest[:12]+'.zip',sha256=digest),run_suffix='uefn_locomotion_final_blend50_1024')
    d.save('final-phase-prepared',plan)
    report=dict(count=lib.get_num_motions()*count,blend_min=float(new['plus_blend'].min()),blend_max=float(new['plus_blend'].max()),blend_mean=float(new['plus_blend'].mean()),floor_lift_max_m=max_floor_lift,minimum_clearance_m=min_clearance,bank_sha256=sha,checkpoint=plan['checkpoint']['key'])
    (out/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
