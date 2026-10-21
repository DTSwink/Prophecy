"""Refresh only policy motion copies and verify planted hands at 240 Hz."""
import json,pickle,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
import repair_references as rr
from replay_selection import patch,select_replay_worlds

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/MimicKitCrawl';PACKAGE=OUT/'package'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    model=rr.ae.rt.MJCFCharModel('cpu');model.load(str(PACKAGE/'assets/uefn/humanoid_uefn.xml'))
    names=model.get_body_names();geo=json.loads((OUT/'geometry.json').read_text())
    corrections=json.loads((OUT/'corrected-references/report.json').read_text());checks=[];audits=[]
    meta=json.loads((PACKAGE/'assets/uefn/limits.json').read_text())
    manifest=json.loads((PACKAGE/'prepared/manifest.json').read_text())
    for row,correction in zip(manifest['motions'],corrections['motions']):
        p=Path(correction['file']);motion=pickle.loads(p.read_bytes());f=motion['frames'].copy()
        forward=-(R.from_rotvec(f[0,3:6]).as_matrix()[:2,0]);yaw=float(np.arctan2(forward[1],forward[0]));turn=R.from_euler('z',-yaw)
        origin=f[0,:3].copy();origin[2]=0
        f[:,:3]=turn.apply(f[:,:3]-origin);f[:,3:6]=(turn*R.from_rotvec(f[:,3:6])).as_rotvec()
        motion['frames']=f;motion['loop_mode']=1
        dest=PACKAGE/'motions'/(row['id']+'.pkl');dest.write_bytes(pickle.dumps(motion))
        row.update(source=str(p),source_sha256=sha(p),initial_yaw_removed_rad=yaw,frames=len(f),fps=motion['fps'],duration=(len(f)-1)/motion['fps'])
        times=np.arange(len(f));dense=np.linspace(0,len(f)-1,(len(f)-1)*8+1)
        ff=np.stack([np.interp(dense,times,f[:,i]) for i in range(f.shape[1])],-1)
        channels=[3]+[6+model.get_joint(j).dof_idx for j in range(1,model.get_num_joints()) if model.get_joint(j).get_dof_dim()==3]
        for start in channels:ff[:,start:start+3]=Slerp(times,R.from_rotvec(f[:,start:start+3]))(dense).as_rotvec()
        pp,qq=rr.ae.fk(model,ff.astype(np.float32));rot=R.from_quat(qq.reshape(-1,4)).as_matrix().reshape(len(ff),len(names),3,3)
        hands=[]
        for k,name in enumerate(('right_hand','left_hand')):
            j=names.index(name);g=next(x for x in geo['shapes'] if x['bone']==name)
            bottom=pp[:,j,2]+(rot[:,j]@np.array(g['position']))[:,2]-np.abs((rot[:,j]@np.array(g['axes']))[:,2,:])@(np.array(g['dimensions'])/2)
            desired=np.array(correction['hand_contact']['clearance_m'])[:,k] if row['id']=='crawl' else np.zeros(len(f))
            error=bottom[::8]-desired
            planted=(np.interp(dense,times,(desired==0).astype(float))>.9999)
            hands.append(dict(name=name,keyframe_error_m=float(abs(error).max()),dense_minimum_m=float(bottom.min()),dense_planted_max_abs_m=float(abs(bottom[planted]).max()),swing_max_m=float(bottom.max())))
            assert abs(error).max()<2e-6
            assert bottom.min()>-.003 and abs(bottom[planted]).max()<.003,hands[-1]
        old=pickle.loads((OUT/'stopped-run-20261017_065646/package-motions'/dest.name).read_bytes())['frames']
        factor=(len(f)-1)//(len(old)-1)
        np.testing.assert_allclose(f[::factor,:6],old[:,:6],rtol=0,atol=3e-7)
        for name in names:
            if any(v in name for v in ('thigh','shin','foot')):
                joint=model.get_joint(names.index(name));start=6+joint.dof_idx
                np.testing.assert_allclose(f[::factor,start:start+joint.get_dof_dim()],old[:,start:start+joint.get_dof_dim()],rtol=0,atol=3e-7)
        checks.append(dict(clip=row['id'],sha256=sha(dest),hands=hands,root_legs_unchanged=True))
        audit=[]
        for joint in meta['joints']:
            coords,_=rr.ae.rt.sampled_coordinates(model,joint,f,1)
            audit.append(dict(body=joint['body'],outside_frames=int(rr.ae.rt.violation(coords,joint).sum()),frames=len(f)))
        audits.append(dict(id=row['id'],joints=audit))
    (PACKAGE/'prepared/manifest.json').write_text(json.dumps(manifest,indent=2))
    (OUT/'prepared/manifest.json').write_text(json.dumps(manifest,indent=2).replace('/workspace/mimickit_trial',PACKAGE.as_posix()))
    (OUT/'reference-limit-audit.json').write_text(json.dumps(audits,indent=2))
    patch(PACKAGE)
    for round in range(40):
        ids=select_replay_worlds([1]*20+[0]*492,20,[False,False],12,round)
        assert len(set(ids))==12 and sum(i<20 for i in ids)==1
    result=dict(passed=True,checks=checks,replay_idle_rows=1,replay_crawl_rows=11,physics_hz=240)
    (OUT/'contact-cleanup-validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
