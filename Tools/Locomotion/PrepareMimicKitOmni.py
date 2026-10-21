"""Prepare candidate reduced-body references; never alter accepted recordings.

Transfers anchor rotations into the existing reduced hierarchy. Omitted chains
cannot follow independently: residuals are reported, not
hidden with a global pose fit, limit clamp or stretch. User-authorized vertical
foot correction preserves each leg's pole and the pelvis. No seamless fitting.
"""
from pathlib import Path
import json, pickle, sys
import numpy as np
import torch
import yaml
from scipy.spatial.transform import Rotation as R

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit'))
from anim.mjcf_char_model import MJCFCharModel
from anim.kin_char_model import JointType
from RetargetFootLift import lift_feet

def matrix(row):
    a=np.eye(4);a[:3,:3]=R.from_quat(row[3:]).as_matrix();a[:3,3]=np.array(row[:3])*.01
    return a

def serialized(row):
    a=np.eye(4);a[:3,:3]=R.from_quat(row['quaternion']).as_matrix();a[:3,3]=row['position'];return a

def main(clips=None, output=None, source_folder=None, write_preview=True, preview_path=None):
    torch.set_num_threads(1)
    folder=ROOT/'Labs/MimicKitUEFN'
    output=Path(output) if output is not None else ROOT/'Saved/MimicKitUEFN/omni';output.mkdir(parents=True,exist_ok=True)
    source_folder=Path(source_folder) if source_folder is not None else ROOT/'Saved/Diagnostics/OmniRecord20261015'
    meta=json.loads((folder/'limits.json').read_text())
    source=json.loads((ROOT/meta.get('source_rig','Saved/Robotics/rig.json')).read_text())
    ref={b['name']:matrix(b['reference']['position_cm']+b['reference']['rotation_xyzw']) for b in source['bodies']}
    model=MJCFCharModel('cpu');model.load(str(folder/'humanoid_uefn.xml'))
    names=model.get_body_names();parents=np.asarray(model._parent_indices)
    asset_basis=np.eye(4);asset_basis[:3,:3]=R.from_euler('z',90,degrees=True).as_matrix()
    # Recorded mesh forward is +Y (verified from head/feet). Rotate it to +X.
    # Asset basis itself is unchanged; anchor offsets bridge the two frames.
    motion_basis=np.eye(4);motion_basis[:3,:3]=R.from_euler('z',-90,degrees=True).as_matrix()
    offsets={n:np.linalg.inv(ref[meta['groups'][n]['anchor']])@np.linalg.inv(asset_basis)@serialized(meta['body_frames'][n]) for n in names}
    if clips is None:clips=json.loads((ROOT/'Labs/OmniLocomotionViewer/data.json').read_text())['clips']
    manifest=[];files=[];preview=[]
    for clip in clips:
        raw=json.loads((source_folder/(clip['id']+'.json')).read_text())
        cut=clip['cut'];frames=np.asarray([r['pose'] for r in raw['rows'][cut['start']:cut['end']+1]])
        wanted=np.stack([np.stack([motion_basis@matrix(f[raw['names'].index(meta['groups'][n]['anchor'])])@offsets[n] for n in names]) for f in frames])
        count=len(frames);dof=np.zeros((count,model.get_dof_size()));actual_rot=np.zeros((count,len(names),3,3));actual_rot[:,0]=wanted[:,0,:3,:3]
        local_rot=R.from_quat(model._local_rotation.numpy()).as_matrix()
        for j in range(1,len(names)):
            parent=int(parents[j]);joint=model.get_joint(j)
            delta=np.swapaxes(local_rot[j],-1,-2)@np.swapaxes(actual_rot[:,parent],-1,-2)@wanted[:,j,:3,:3]
            if joint.joint_type==JointType.SPHERICAL:
                dof[:,joint.dof_idx:joint.dof_idx+3]=R.from_matrix(delta).as_rotvec();qr=delta
            elif joint.joint_type==JointType.HINGE:
                q=R.from_matrix(delta).as_quat();axis=joint.axis.numpy();angle=2*np.arctan2(q[:,:3]@axis,q[:,3]);angle=(angle+np.pi)%(2*np.pi)-np.pi
                dof[:,joint.dof_idx]=angle;qr=R.from_rotvec(angle[:,None]*axis).as_matrix()
            else:qr=np.broadcast_to(np.eye(3),(count,3,3))
            actual_rot[:,j]=actual_rot[:,parent]@local_rot[j]@qr
        root_p=wanted[:,0,:3,3];root_q=R.from_matrix(actual_rot[:,0]).as_quat()
        dp=torch.tensor(dof,dtype=torch.float32)
        p,q=model.forward_kinematics(torch.tensor(root_p,dtype=torch.float32),torch.tensor(root_q,dtype=torch.float32),model.dof_to_rot(dp))
        before_p=p.numpy().copy();before_q=q.numpy().copy()
        # Each leg is solved independently from the same original frame.
        # Only added penetration is removed; original floor intersection stays.
        corrections=lift_feet(model,names,meta,wanted,before_p,actual_rot,dof)
        p,q=model.forward_kinematics(torch.tensor(root_p,dtype=torch.float32),torch.tensor(root_q,dtype=torch.float32),model.dof_to_rot(torch.tensor(dof,dtype=torch.float32)))
        actual_rot=R.from_quat(q.numpy().reshape(-1,4)).as_matrix().reshape(count,len(names),3,3)
        leg_ids={names.index(side+'_'+part) for side in ('right','left') for part in ('thigh','shin','foot')}
        fixed=[i for i in range(len(names)) if i not in leg_ids]
        np.testing.assert_array_equal(p.numpy()[:,fixed],before_p[:,fixed])
        np.testing.assert_array_equal(q.numpy()[:,fixed],before_q[:,fixed])
        for side in ('right','left'):
            changed={c['tick'] for c in corrections if c['side']==side}
            untouched=[t for t in range(count) if t not in changed]
            ids=[names.index(side+'_'+part) for part in ('thigh','shin','foot')]
            np.testing.assert_array_equal(p.numpy()[untouched][:,ids],before_p[untouched][:,ids])
            np.testing.assert_array_equal(q.numpy()[untouched][:,ids],before_q[untouched][:,ids])
        foot_orientation_roundtrip=0.
        for c in corrections:
            t=c['tick'];fi=names.index(c['side']+'_foot');ki=names.index(c['side']+'_shin')
            # Float32 FK over this chain can accumulate ~0.6 micrometres even
            # without travel; recordings with ~10m travel need relative ULPs.
            np.testing.assert_allclose(p.numpy()[t,fi],c['target'],atol=1e-6,rtol=2e-7)
            np.testing.assert_allclose(p.numpy()[t,ki],c['knee'],atol=1e-6,rtol=2e-7)
            # Float32 exp-map/FK round trips accumulate ~1e-6 rad. Check the
            # rotation itself, not an individual near-zero matrix entry.
            angular_error=(R.from_matrix(actual_rot[t,fi]).inv()*R.from_quat(before_q[t,fi])).magnitude()
            foot_orientation_roundtrip=max(foot_orientation_roundtrip,float(angular_error))
            assert angular_error<=2e-6,(clip['id'],t,angular_error)
        pos_error=np.linalg.norm(p.numpy()-wanted[:,:,:3,3],axis=-1)
        rot_error=np.degrees(R.from_matrix((np.swapaxes(actual_rot,-1,-2)@wanted[:,:,:3,:3]).reshape(-1,3,3)).magnitude()).reshape(count,-1)
        # Phase zero = left foot's lowest forward-relative speed (stance centre),
        # independently of arbitrary cut boundary or motion travel direction.
        li=names.index('left_foot');foot_rel=p.numpy()[:,li]-p.numpy()[:,0]
        travel=np.array(raw['velocity_mesh_cm_s']);speed=np.linalg.norm(travel[:2])
        if clip['gait']=='idle':
            assert speed==0
            command=np.array([1.,0.]);phase_zero=0
        else:
            assert speed>0
            command=np.array([travel[1],-travel[0]])/speed
            world_forward=motion_basis[:3,:3]@(travel/speed)
            along=foot_rel@world_forward
            phase_zero=int(np.argmin(np.gradient(along,1/60)[:-1]))
        phase_offset=(-phase_zero/(count-1))%1.
        saved=np.concatenate([root_p,R.from_quat(root_q).as_rotvec(),dof],axis=1)
        path=output/(clip['id']+'.pkl')
        with path.open('wb') as f:pickle.dump({'loop_mode':1,'fps':60,'frames':saved.astype(np.float32)},f)
        row=dict(id=clip['id'],gait={'idle':-1,'walk':0,'run':1}[clip['gait']],direction=command.tolist(),duration=(count-1)/60,
                 phase_offset=phase_offset,phase_zero_tick=phase_zero,source_cut=cut,
                 position_max_cm=float(pos_error.max()*100),position_rms_cm=float(np.sqrt(np.mean(pos_error**2))*100),
                 rotation_max_deg=float(rot_error.max()),per_body_position_max_cm=dict(zip(names,(pos_error.max(0)*100).tolist())),
                 foot_lift=dict(corrected_foot_frames=len(corrections),max_cm=max((c['lift_cm'] for c in corrections),default=0.),
                                max_orientation_roundtrip_rad=foot_orientation_roundtrip),
                 per_body_rotation_max_deg=dict(zip(names,rot_error.max(0).tolist())))
        manifest.append(row);files.append(dict(file=str(path),weight=1.))
        source_names=list(ref)
        source_frames=np.stack([np.stack([motion_basis@matrix(f[raw['names'].index(n)]) for n in source_names]) for f in frames])
        source_pose=np.concatenate([source_frames[:,:,:3,3],R.from_matrix(source_frames[:,:,:3,:3].reshape(-1,3,3)).as_quat().reshape(count,-1,4)],-1)
        preview.append(dict(id=clip['id'],label=clip['label'],gait=clip['gait'],
                            source=np.round(source_pose,7).tolist(),
                            reduced=np.round(np.concatenate([p.numpy(),q.numpy()],-1),7).tolist(),metrics=row))
        print(clip['id'],f"position max {row['position_max_cm']:.2f}cm, rotation max {row['rotation_max_deg']:.2f}deg")
    (output/'motions.yaml').write_text(yaml.safe_dump({'motions':files}))
    (output/'manifest.json').write_text(json.dumps(dict(status='candidate_not_approved_for_training',body_names=names,motions=manifest),indent=2))
    if not write_preview:return manifest
    overlay=json.loads((folder/'overlay-data.json').read_text())
    def local_geometry(layer,rest):
        result=[]
        for g in overlay[layer]:
            body=g['name'].rsplit('_shape',1)[0] if layer=='phat' else g['body']
            local=np.linalg.inv(serialized(rest[body]))@serialized(g)
            result.append(dict(g,body=body,position=local[:3,3].tolist(),quaternion=R.from_matrix(local[:3,:3]).as_quat().tolist()))
        return result
    viewer=dict(fps=60,names=names,source_names=source_names,clips=preview,
                geometry=local_geometry('new',meta['body_frames']),
                source_geometry=local_geometry('phat',overlay['meta']['source_body_frames']))
    destination=Path(preview_path) if preview_path else folder/'omni-preview.json'
    destination.write_text(json.dumps(viewer,separators=(',',':')),encoding='utf-8')

if __name__=='__main__':main()

