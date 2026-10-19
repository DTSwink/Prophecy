"""Clear initially underground feet using fixed-hip/pole IK; reset data only."""
import json,pickle,hashlib
from prepare_recovery_hand_ik import ROOT,ae,np,torch,R,solve_leg,box_bottom

def main(output=None):
    from pathlib import Path
    torch.set_num_threads(1);out=Path(output) if output is not None else ROOT/'Saved/MimicKitEquipment/recovery-preview'
    model=ae.rt.MJCFCharModel('cpu');model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    names=model.get_body_names();meta=json.loads((ROOT/'Labs/MimicKitUEFN/limits.json').read_text())
    lr=R.from_quat(model._local_rotation.numpy()).as_matrix();lp=model._local_translation.numpy()
    reports=[];pending=[];preview=json.loads((out/'data.json').read_text())
    for name in ('getUp_front_quick','getUp_back_quick'):
        source=out/(name+'_reset_hand_ik.pkl');data=pickle.loads(source.read_bytes());original=data['frames']
        frames=original.astype(np.float64).copy();p,q=ae.fk(model,frames)
        rot=R.from_quat(q.reshape(-1,4)).as_matrix().reshape(len(frames),len(names),3,3)
        columns=[];changes=[]
        for side in ('right','left'):
            hi,ki,fi=[names.index(side+'_'+part) for part in ('thigh','shin','foot')]
            hj,kj,fj=[model.get_joint(j) for j in (hi,ki,fi)]
            columns.extend([6+hj.dof_idx+i for i in range(3)]+[6+kj.dof_idx]+[6+fj.dof_idx+i for i in range(3)])
            rest=meta['body_frames'][side+'_foot'];rr=R.from_quat(rest['quaternion']).as_matrix()
            g=next(g for g in meta['geometry'] if g['body']==side+'_foot')
            gp=rr.T@(np.array(g['position'])-rest['position']);gr=rr.T@R.from_quat(g['quaternion']).as_matrix();size=np.array(g['size'])
            for tick in range(len(frames)):
                low=box_bottom(p[tick,fi],rot[tick,fi],gp,gr,size)
                if low>=0.:continue
                target=p[tick,fi].astype(np.float64).copy();target[2]+=-low+1e-6
                hr,angle,kr,kp=solve_leg(p[tick,hi],p[tick,ki],p[tick,fi],target,lp[ki],lp[fi],lr[ki],kj.axis.numpy(),frames[tick,6+kj.dof_idx])
                parent=int(model._parent_indices[hi])
                frames[tick,6+hj.dof_idx:9+hj.dof_idx]=R.from_matrix(lr[hi].T@rot[tick,parent].T@hr).as_rotvec()
                frames[tick,6+kj.dof_idx]=angle
                frames[tick,6+fj.dof_idx:9+fj.dof_idx]=R.from_matrix(lr[fi].T@kr.T@rot[tick,fi]).as_rotvec()
                changes.append(dict(side=side,frame=tick,lift_cm=(-low+1e-6)*100,target=target.tolist()))
        frames=frames.astype(np.float32);p2,q2=ae.fk(model,frames)
        untouched=[i for i in range(frames.shape[1]) if i not in columns]
        np.testing.assert_array_equal(frames[:,untouched],original[:,untouched])
        for c in changes:
            t=c['frame'];b=names.index(c['side']+'_foot')
            np.testing.assert_allclose(p2[t,b],c['target'],atol=2e-6,rtol=0)
            assert (R.from_quat(q2[t,b]).inv()*R.from_quat(q[t,b])).magnitude()<3e-6
        data['frames']=frames;pending.append((out/(name+'_reset_floor_ik.pkl'),pickle.dumps(data)))
        pose=np.concatenate((p2,q2),-1);pose[:,:,:2]-=p2[0,0,:2]
        next(c for c in preview['clips'] if c['id']==name)['reset_poses']=pose.round(7).tolist()
        reports.append(dict(motion=name,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),corrections=changes,
            max_lift_cm=max(c['lift_cm'] for c in changes),root_upper_body_and_hands_exact=True,foot_orientation_preserved=True))
    for path,data in pending:path.write_bytes(data)
    (out/'foot-reset-ik-report.json').write_text(json.dumps(dict(reset_only=True,target_unchanged=True,clips=reports),indent=2))
    (out/'data.json').write_text(json.dumps(preview,separators=(',',':')))
    print(json.dumps([{k:v for k,v in r.items() if k!='corrections'}|dict(corrected_frames=len(r['corrections'])) for r in reports]),flush=True)
if __name__=='__main__':main()
