"""Validate and publish the isolated contact-IK comparison; no deployment."""
import json, os, pickle, subprocess
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
from constrained_contact import ROOT, load, sampled_coordinates, violation, sha
from upperarm_pose_audit import poses


def densify(model,frames,factor=8):
    times=np.arange(len(frames));q=np.linspace(0,len(frames)-1,(len(frames)-1)*factor+1)
    dense=np.stack([np.interp(q,times,frames[:,i]) for i in range(frames.shape[1])],-1)
    channels=[3]+[6+model.get_joint(j).dof_idx for j in range(1,model.get_num_joints()) if model.get_joint(j).get_dof_dim()==3]
    for s in channels:dense[:,s:s+3]=Slerp(times,R.from_rotvec(frames[:,s:s+3]))(q).as_rotvec()
    return dense


def main():
    ik,motion,old,original=load();out=ROOT/'Saved/MimicKitCrawl/constrained-ik'
    candidate=pickle.loads((out/'crawl.pkl').read_bytes())['frames']
    constrained=['right_upper_arm','left_upper_arm','right_lower_arm','left_lower_arm','right_hand','left_hand']
    checks=[];probe=[]
    for j in ik.meta['joints']:
        before,_=sampled_coordinates(ik.model,j,old,8)
        after,q=sampled_coordinates(ik.model,j,candidate,8)
        checks.append(dict(body=j['body'],samples=len(after),before_outside=int(violation(before,j).sum()),
            after_outside=int(violation(after,j).sum()),max_twist_before_deg=float(np.rad2deg(abs(before[:,0]).max())),
            max_twist_after_deg=float(np.rad2deg(abs(after[:,0]).max()))))
        if j['body'] in constrained:
            assert not violation(after,j).any(),checks[-1]
            for quat in q:probe.append([len(probe),*j['modes'],*j['limits_rad'],*quat])
    np.savetxt(out/'jolt-input.csv',probe,delimiter=',',header='index,m0,m1,m2,a,b,c,w,x,y,z',comments='',fmt='%.12g')
    env=dict(os.environ);env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env['PATH']
    subprocess.run([str(ROOT/'Saved/Robotics/jolt_probe.exe'),'--limits',str(out/'jolt-input.csv'),str(out/'jolt-output.csv')],env=env,check=True,capture_output=True)
    result=np.genfromtxt(out/'jolt-output.csv',names=True,delimiter=',')
    assert not (result['mask']!=0).any(),'Jolt rejected dense arm sample'
    dense_old=poses(ik.model,densify(ik.model,old));dense_new=poses(ik.model,densify(ik.model,candidate))
    geo=json.loads((ROOT/'Saved/MimicKitCrawl/geometry.json').read_text())
    correction=json.loads((ROOT/'Saved/MimicKitCrawl/corrected-references/report.json').read_text())['motions'][0]
    clear=np.array(correction['hand_contact']['clearance_m'])
    hands=[]
    for h,name in enumerate(('right_hand','left_hand')):
        k=ik.ids[name];g=next(x for x in geo['shapes'] if x['bone']==name)
        q=R.from_quat(dense_new[:,k,3:]);rot=q.as_matrix()
        bottom=dense_new[:,k,2]+(rot@np.array(g['position']))[:,2]-np.abs((rot@np.array(g['axes']))[:,2,:])@(np.array(g['dimensions'])/2)
        planted=np.interp(np.arange(len(bottom))/8,np.arange(len(clear)),(clear[:,h]==0).astype(float))>.9999
        position=np.linalg.norm(dense_new[:,k,:3]-dense_old[:,k,:3],axis=-1)
        rotation=(R.from_quat(dense_old[:,k,3:]).inv()*q).magnitude()
        hand=dict(body=name,key_position_error_m=float(position[::8].max()),dense_position_error_m=float(position.max()),
            dense_orientation_error_deg=float(np.rad2deg(rotation.max())),minimum_floor_gap_m=float(bottom.min()),
            planted_max_floor_gap_m=float(abs(bottom[planted]).max()))
        hands.append(hand)
        assert hand['key_position_error_m']<2e-6,hand
        assert hand['dense_position_error_m']<.003,hand
        assert hand['planted_max_floor_gap_m']<.003,hand
        assert hand['minimum_floor_gap_m']>-.003,hand
    np.testing.assert_array_equal(candidate[:,:6],old[:,:6].astype(np.float32))
    for name in ik.names:
        if any(x in name for x in ('thigh','shin','foot')):
            np.testing.assert_array_equal(candidate[:,ik.slices[name]],old[:,ik.slices[name]].astype(np.float32))
    allposes=[poses(ik.model,x) for x in (old,candidate,original)]
    pp=allposes[1]
    relative=pp[:,:,:3]-pp[:,:1,:3]
    seam=float(np.linalg.norm(relative[-1]-relative[0],axis=-1).max())
    step=R.from_quat(pp[:-1,:,3:].reshape(-1,4)).inv()*R.from_quat(pp[1:,:,3:].reshape(-1,4))
    maxstep=float(np.rad2deg(step.magnitude()).max())
    assert seam<2e-6,seam
    assert maxstep<5.,('Pose discontinuity',maxstep)
    report=dict(passed=True,arm_constraints=constrained,jolt_samples=len(probe),hands=hands,limits=checks,
        root_legs_unchanged=True,loop_seam_m=seam,max_adjacent_body_rotation_deg=maxstep,
        source_sha256=sha(ROOT/'Saved/MimicKitCrawl/package/motions/crawl.pkl'),candidate_sha256=sha(out/'crawl.pkl'),
        limits_sha256=sha(ROOT/'Saved/MimicKitCrawl/package/assets/uefn/limits.json'),
        scope='Both shoulders/elbows/wrists within current PHAT; exact previous hand transforms at keys; pelvis/legs unchanged. Torso, head and left ankle remaining conflicts are reported, not silently fixed. Candidate only, not installed for training.')
    (out/'verification.json').write_text(json.dumps(report,indent=2))
    audit=json.loads((ROOT/'Saved/MimicKitCrawl/upperarm-pose-audit/data.json').read_text())
    centered=[]
    for p in allposes:
        p[:,:,:2]-=p[:,:1,:2].copy();centered.append(p.round(6).tolist())
    doc=dict(bodies=audit['bodies'],fps=motion['fps'],frames=len(candidate),before=centered[0],after=centered[1],original=centered[2],
        report=report,default_frame=280,arm_indices=[ik.ids[n] for n in constrained])
    (out/'data.json').write_text(json.dumps(doc,separators=(',',':')))
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
