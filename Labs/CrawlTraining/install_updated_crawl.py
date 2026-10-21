"""Verify and install only the new crawl reference; preserve existing planted idle."""
import json,os,pickle,shutil,subprocess
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
from constrained_contact import ContactIK, sampled_coordinates, violation
from current_phat import verify_current_phat,sha
from fit_motion_limits import inflate
from upperarm_pose_audit import quaternion
from verify_constrained_contact import densify
from upperarm_pose_audit import poses, MJCFCharModel
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/MimicKitCrawl';CAND=OUT/'updated-training-20261017';PACKAGE=OUT/'package'

def main():
    meta=verify_current_phat(PACKAGE/'assets/uefn')
    model=MJCFCharModel('cpu');model.load(str(PACKAGE/'assets/uefn/humanoid_uefn.xml'))
    names=model.get_body_names();geo=json.loads((OUT/'geometry.json').read_text())
    motion=pickle.loads((CAND/'crawl.pkl').read_bytes());frames=motion['frames']
    base=pickle.loads((CAND/'contact-target.pkl').read_bytes())['frames']
    np.testing.assert_array_equal(frames[:,:6],base[:,:6])
    for name in names:
        if any(s in name for s in ('thigh','shin','foot')):
            k=model.get_joint(names.index(name));start=6+k.dof_idx
            np.testing.assert_array_equal(frames[:,start:start+k.get_dof_dim()],base[:,start:start+k.get_dof_dim()])
    f=frames.copy();forward=-R.from_rotvec(f[0,3:6]).as_matrix()[:2,0];yaw=float(np.arctan2(forward[1],forward[0]));turn=R.from_euler('z',-yaw)
    origin=f[0,:3].copy();origin[2]=0;f[:,:3]=turn.apply(f[:,:3]-origin);f[:,3:6]=(turn*R.from_rotvec(f[:,3:6])).as_rotvec()
    motion['frames']=f
    checks=[];probe=[]
    idle=pickle.loads((PACKAGE/'motions/crawl_idle.pkl').read_bytes())
    for label,m in [('crawl',motion),('crawl_idle',idle)]:
        values=m['frames'];factor=8 if label=='crawl' else 64
        pp=poses(model,densify(model,values,factor));rot=R.from_quat(pp[:,:,3:].reshape(-1,4)).as_matrix().reshape(len(pp),len(names),3,3)
        hands=[]
        clear=np.array(json.loads((CAND/'contact-target.json').read_text())['clearance_m']) if label=='crawl' else np.zeros((len(values),2))
        for h,name in enumerate(('right_hand','left_hand')):
            i=names.index(name);g=next(s for s in geo['shapes'] if s['bone']==name)
            bottom=pp[:,i,2]+(rot[:,i]@np.array(g['position']))[:,2]-np.abs((rot[:,i]@np.array(g['axes']))[:,2,:])@(np.array(g['dimensions'])/2)
            planted=np.interp(np.arange(len(pp))/factor,np.arange(len(values)),(clear[:,h]==0).astype(float))>.9999
            row=dict(body=name,minimum_m=float(bottom.min()),planted_max_abs_m=float(abs(bottom[planted]).max()))
            assert row['minimum_m']>-.003 and row['planted_max_abs_m']<.003,row
            hands.append(row)
        audit=[]
        for j in meta['joints']:
            v,q=sampled_coordinates(model,j,values,factor);bad=violation(v,j)
            audit.append(dict(body=j['body'],outside=int(bad.sum()),samples=len(v)))
            if not any(s in j['body'] for s in ('thigh','shin','foot')):
                assert not bad.any(),(label,audit[-1])
                margin=inflate(v,1.05)
                assert not violation(margin,j).any(),('5% room',label,j['body'])
                for quat in q:probe.append([len(probe),*j['modes'],*j['limits_rad'],*quat])
                for vmargin in margin:probe.append([len(probe),*j['modes'],*j['limits_rad'],*quaternion(vmargin)])
        rel=pp[:,:,:3]-pp[:,:1,:3];seam=float(np.linalg.norm(rel[-1]-rel[0],axis=-1).max());assert seam<2e-6,seam
        keys=pp[::factor];step=(R.from_quat(keys[:-1,:,3:].reshape(-1,4)).inv()*R.from_quat(keys[1:,:,3:].reshape(-1,4))).magnitude()
        peak=float(np.rad2deg(step.max()));assert peak<5.,(label,peak)
        checks.append(dict(clip=label,hands=hands,limit_audit=audit,loop_seam_m=seam,max_key_rotation_deg=peak))
    np.savetxt(CAND/'jolt-input.csv',probe,delimiter=',',header='index,m0,m1,m2,a,b,c,w,x,y,z',comments='',fmt='%.12g')
    env=dict(os.environ);env['PATH']=str(ROOT/'Intermediate/JoltMigration/Install/Development/bin')+os.pathsep+env['PATH']
    subprocess.run([str(ROOT/'Saved/Robotics/jolt_probe.exe'),'--limits',str(CAND/'jolt-input.csv'),str(CAND/'jolt-output.csv')],env=env,check=True,capture_output=True)
    result=np.genfromtxt(CAND/'jolt-output.csv',names=True,delimiter=',');assert not np.any(result['mask'])
    backup=CAND/'before-package-five-percent';backup.mkdir(exist_ok=False)
    for p in (PACKAGE/'motions').glob('*.pkl'):shutil.copy2(p,backup/p.name)
    manifest=json.loads((PACKAGE/'prepared/manifest.json').read_text());shutil.copy2(PACKAGE/'prepared/manifest.json',backup/'manifest.json')
    target=PACKAGE/'motions/crawl.pkl';target.write_bytes(pickle.dumps(motion))
    entry=next(r for r in manifest['motions'] if r['id']=='crawl')
    entry.update(source=str(CAND/'crawl.pkl'),source_sha256=sha(CAND/'crawl.pkl'),frames=len(f),fps=motion['fps'],duration=(len(f)-1)/motion['fps'],initial_yaw_removed_rad=yaw)
    (PACKAGE/'prepared/manifest.json').write_text(json.dumps(manifest,indent=2))
    (OUT/'prepared/manifest.json').write_text(json.dumps(manifest,indent=2).replace('/workspace/mimickit_trial',PACKAGE.as_posix()))
    for row in checks:row['sha256']=sha(PACKAGE/'motions'/(row['clip']+'.pkl'))
    doc=dict(passed=True,clips=checks,limits_sha256=sha(PACKAGE/'assets/uefn/limits.json'),jolt_samples=len(probe),
        upperbody_within_limits=True,angular_margin_factor=1.05,legs_and_phat_unchanged=True,idle_unchanged=True,scope='Updated crawl, fixed authored hand targets with floor clearance, continuous loop, upper-body constraints with 5% angular room. Existing ankle conflicts intentionally retained.')
    (CAND/'verification.json').write_text(json.dumps(doc,indent=2));print(json.dumps(doc),flush=True)

if __name__=='__main__':main()
