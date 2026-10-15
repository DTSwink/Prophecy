"""Independent geometry/FK, exact Jolt limit classification and solver tests."""
import json
from pathlib import Path
import os
import sys
import subprocess
import numpy as np
import mujoco
from scipy.spatial.transform import Rotation as R

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def coords(q):
    w,x,y,z=np.moveaxis(q,-1,0);n=np.maximum(np.hypot(w,x),1e-12)
    return np.stack([(2*np.arctan2(x,w)+np.pi)%(2*np.pi)-np.pi,(w*y-x*z)/n,(x*y+w*z)/n],axis=-1)

def violation(v,j):
    modes=j['modes'];lim=j['limits_rad'];tol=2e-6
    bad=np.abs(v[...,0])>(lim[0] if modes[0]==1 else 0)+tol
    if modes[1]==modes[2]==1:
        bad|=(v[...,1]/np.sin(lim[1]/2))**2+(v[...,2]/np.sin(lim[2]/2))**2>1+tol
    else:
        for k in (1,2):bad|=np.abs(v[...,k])>(np.sin(lim[k]/2) if modes[k]==1 else 0)+tol
    return bad

def test_fk(meta):
    import torch
    sys.path.insert(0,str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit'))
    from anim.mjcf_char_model import MJCFCharModel
    torch.set_num_threads(1)
    k=MJCFCharModel('cpu');k.load(str(HERE/'humanoid_uefn.xml'))
    old=MJCFCharModel('cpu');old.load(str(ROOT/'Saved/MimicKit/vendor/MimicKit/data/assets/humanoid/humanoid.xml'))
    assert k.get_body_names()==old.get_body_names()
    assert old.get_dof_size()==28 and k.get_dof_size()==meta['action_dimensions']==34
    m=mujoco.MjModel.from_xml_path(str(HERE/'humanoid_uefn_physics.xml'));d=mujoco.MjData(m)
    rng=np.random.default_rng(764);worst=0.
    for _ in range(30):
        dof=torch.tensor(rng.normal(size=(1,k.get_dof_size()))*.2,dtype=torch.float32)
        jq=k.dof_to_rot(dof)
        pos=torch.tensor([meta['body_frames']['pelvis']['position']],dtype=torch.float32)
        rot=torch.tensor([[0.,0.,0.,1.]])
        kp,kr=k.forward_kinematics(pos,rot,jq)
        d.qpos[:]=m.qpos0
        for i,name in enumerate(k.get_body_names()):
            if not i:continue
            j=next((j for j in meta['joints'] if j['body']==name),None)
            if not j:continue
            adr=m.joint(j['name']).qposadr[0]
            if j['kind']=='ball':d.qpos[adr:adr+4]=jq[0,i-1].numpy()[[3,0,1,2]]
            else:d.qpos[adr]=k.get_joint(i).get_joint_dof(dof)[0,0]
        mujoco.mj_forward(m,d)
        for i,name in enumerate(k.get_body_names()):
            b=m.body(name).id
            error=np.linalg.norm(kp[0,i].numpy()-d.xpos[b]);worst=max(worst,float(error))
            q=kr[0,i].numpy()[[3,0,1,2]]
            assert min(np.linalg.norm(q-d.xquat[b]),np.linalg.norm(q+d.xquat[b]))<2e-6
    assert worst<1e-6
    return dict(random_poses=30,max_position_error_m=worst,unchanged_body_names=True,action_dimensions=k.get_dof_size())

def test_jolt(meta,out):
    rng=np.random.default_rng(293);values=[];predicted=[]
    for j in meta['joints']:
        for _ in range(300):
            if j['kind']=='ball':
                delta=R.from_rotvec(rng.normal(size=3)*.8)
                q=(R.from_quat(np.array(j['reference_wxyz'])[[1,2,3,0]])*delta).as_quat()[[3,0,1,2]]
            else:
                delta=rng.uniform(-3,3)
                ref=R.from_quat(np.array(j['reference_wxyz'])[[1,2,3,0]]).as_rotvec()
                # Exported connector rotations have <3e-6 rad locked-axis
                # rounding residue. A true hinge has exactly one axis.
                assert np.linalg.norm(ref[:2])<1e-5
                q=R.from_rotvec([0,0,ref[2]+delta]).as_quat()[[3,0,1,2]]
                expected=not j['range_rad'][0]<=delta<=j['range_rad'][1]
                # Angles are modulo 2pi; sample only the non-wrapping range.
                if abs(delta+R.from_quat(np.array(j['reference_wxyz'])[[1,2,3,0]]).as_rotvec()[2])<np.pi:
                    assert bool(violation(coords(q),j))==expected
            predicted.append(bool(violation(coords(q),j)))
            values.append([len(values),*j['modes'],*j['limits_rad'],*q])
    src=out/'limits-input.csv';dst=out/'limits-jolt.csv'
    np.savetxt(src,values,delimiter=',',fmt=['%d']*4+['%.12g']*7,header='index,m0,m1,m2,a,b,c,w,x,y,z',comments='')
    env=dict(os.environ);env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env['PATH']
    subprocess.run([str(ROOT/'Saved/Robotics/jolt_probe.exe'),'--limits',str(src),str(dst)],env=env,check=True,capture_output=True)
    actual=np.genfromtxt(dst,delimiter=',',names=True)
    assert np.array_equal(actual['mask']!=0,predicted)
    return dict(samples=len(values),profiles=len(meta['joints']),admissibility_mismatches=0)

def test_solver(meta,body='right_foot'):
    import warp as wp,mujoco_warp as mjw
    from runtime import install_limits
    wp.init()
    m=mujoco.MjModel.from_xml_path(str(HERE/'humanoid_uefn_physics.xml'))
    m.opt.gravity[:]=0;m.opt.timestep=1/240
    m.opt.disableflags|=mujoco.mjtDisableBit.mjDSBL_CONTACT
    # Remove servos/passive springs for the limit-only test; no changes to asset.
    m.jnt_stiffness[:]=0;m.dof_damping[:]=0
    d=mujoco.MjData(m)
    j=next(j for j in meta['joints'] if j['body']==body)
    adr=m.joint(j['name']).qposadr[0]
    target=R.from_euler('xyz',[75,65,70] if 'hand' in body else [30,25,45],degrees=True)
    d.qpos[adr:adr+4]=(R.from_quat(np.array(j['reference_wxyz'])[[1,2,3,0]]).inv()*target).as_quat()[[3,0,1,2]]
    with wp.ScopedDevice('cpu'):
        wm=mjw.put_model(m);wd=mjw.put_data(m,d,nworld=1,nconmax=1,njmax=100)
        extension=install_limits(m,wm,meta)
        for _ in range(480):mjw.step(wm,wd)
        q=wd.qpos.numpy()[0,adr:adr+4]
        final=(R.from_quat(np.array(j['reference_wxyz'])[[1,2,3,0]])*R.from_quat(q[[1,2,3,0]])).as_quat()[[3,0,1,2]]
        v=coords(final)
        assert np.isfinite(wd.qpos.numpy()).all()
        twist_bound=j['limits_rad'][0] if j['modes'][0]==1 else 0.
        assert abs(v[0])<twist_bound+.005, v
        radius=np.hypot(v[1]/np.sin(j['limits_rad'][1]/2),v[2]/np.sin(j['limits_rad'][2]/2))
        assert radius<1.02,(v,radius)
        expected_locked=sum(j['modes'].count(2) for j in meta['joints'] if j['kind']=='ball')
        assert int(wd.ne.numpy()[0])==expected_locked
    return dict(body=body,cpu_steps=480,twist_rad=float(v[0]),twist_bound_rad=float(twist_bound),swing_ellipse_radius=float(radius),bilateral_rows=expected_locked)

if __name__=='__main__':
    out=ROOT/'Saved/MimicKitUEFN';out.mkdir(exist_ok=True)
    meta=json.loads((HERE/'limits.json').read_text())
    report=dict(fk=test_fk(meta),jolt=test_jolt(meta,out),solver=[test_solver(meta,b) for b in ('right_foot','right_hand','left_hand')],passed=True)
    (out/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
