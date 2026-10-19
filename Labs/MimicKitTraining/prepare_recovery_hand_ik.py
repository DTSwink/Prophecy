"""Precompute hand-clearance IK for recovery resets only; targets unchanged."""
import json,pickle,sys,hashlib
from pathlib import Path
import numpy as np
import torch
from scipy.spatial.transform import Rotation as R
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Labs/RoboticCrawlAE'))
import prepare as ae
from RetargetFootLift import solve_leg,box_bottom

def main(output=None):
    torch.set_num_threads(1)
    out=Path(output) if output is not None else ROOT/'Saved/MimicKitEquipment/recovery-preview'
    model=ae.rt.MJCFCharModel('cpu');model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    names=model.get_body_names();meta=json.loads((ROOT/'Labs/MimicKitUEFN/limits.json').read_text())
    local_r=R.from_quat(model._local_rotation.numpy()).as_matrix();local_p=model._local_translation.numpy()
    reports=[]
    preview=json.loads((out/'data.json').read_text())
    for name in ('getUp_front_quick','getUp_back_quick'):
        source=out/(name+'_robotic.pkl');data=pickle.loads(source.read_bytes());original=data['frames'];frames=original.astype(np.float64).copy()
        p,q=ae.fk(model,frames);rot=R.from_quat(q.reshape(-1,4)).as_matrix().reshape(len(frames),len(names),3,3)
        rows=[];arm_columns=[]
        for side in ('right','left'):
            si,ei,hi=[names.index(side+'_'+part) for part in ('upper_arm','lower_arm','hand')]
            sj,ej,hj=[model.get_joint(j) for j in (si,ei,hi)]
            arm_columns.extend([6+sj.dof_idx+i for i in range(3)]+[6+ej.dof_idx]+[6+hj.dof_idx+i for i in range(3)])
            frame=meta['body_frames'][side+'_hand'];rest=R.from_quat(frame['quaternion']).as_matrix()
            geom=next(g for g in meta['geometry'] if g['body']==side+'_hand')
            assert geom['type']=='box'
            gp=rest.T@(np.array(geom['position'])-frame['position']);gr=rest.T@R.from_quat(geom['quaternion']).as_matrix();size=np.array(geom['size'])
            for tick in range(len(frames)):
                bottom=box_bottom(p[tick,hi],rot[tick,hi],gp,gr,size)
                if bottom>=0:continue
                # One micrometre compensates float32 FK rounding, not a contact gap.
                target=p[tick,hi].astype(np.float64).copy();target[2]+=-bottom+1e-6
                try:
                    sr,angle,er,ep=solve_leg(p[tick,si],p[tick,ei],p[tick,hi],target,local_p[ei],local_p[hi],local_r[ei],ej.axis.numpy(),frames[tick,6+ej.dof_idx])
                except ValueError as error:raise ValueError(f'{name} {side} hand frame {tick}: {error}') from error
                parent=int(model._parent_indices[si])
                frames[tick,6+sj.dof_idx:9+sj.dof_idx]=R.from_matrix(local_r[si].T@rot[tick,parent].T@sr).as_rotvec()
                frames[tick,6+ej.dof_idx]=angle
                frames[tick,6+hj.dof_idx:9+hj.dof_idx]=R.from_matrix(local_r[hi].T@er.T@rot[tick,hi]).as_rotvec()
                rows.append(dict(side=side,frame=tick,lift_cm=(-bottom+1e-6)*100,target=target.tolist()))
        frames=frames.astype(np.float32);p2,q2=ae.fk(model,frames)
        untouched=[i for i in range(40) if i not in arm_columns]
        np.testing.assert_array_equal(frames[:,untouched],original[:,untouched])
        for row in rows:
            t=row['frame'];j=names.index(row['side']+'_hand')
            np.testing.assert_allclose(p2[t,j],row['target'],atol=2e-6,rtol=0)
            assert (R.from_quat(q2[t,j]).inv()*R.from_quat(q[t,j])).magnitude()<3e-6
        data['frames']=frames;(out/(name+'_reset_hand_ik.pkl')).write_bytes(pickle.dumps(data))
        clip=next(c for c in preview['clips'] if c['id']==name)
        shown=np.concatenate((p2,q2),-1);shown[:,:,:2]-=p2[0,0,:2].copy()
        clip['reset_poses']=shown.round(7).tolist()
        reports.append(dict(motion=name,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),corrections=rows,
            max_lift_cm=max((r['lift_cm'] for r in rows),default=0),root_and_lower_body_exact=True,hand_orientation_preserved=True))
    report=dict(reset_only=True,target_unchanged=True,method='Fixed shoulder, original elbow pole and hand orientation; vertical hand lift to collider floor clearance',clips=reports)
    (out/'hand-ik-report.json').write_text(json.dumps(report,indent=2))
    (out/'data.json').write_text(json.dumps(preview,separators=(',',':')))
    print(json.dumps([{k:v for k,v in r.items() if k!='corrections'}|dict(corrected_frames=len(r['corrections'])) for r in reports]),flush=True)
if __name__=='__main__':main()
