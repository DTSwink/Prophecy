"""LAFAN anatomical mapping followed by the current locomotion 15-body retarget.

Writes separate review candidates. Never edits training, PHAT or source cuts.
Run with Saved/Robotics/env/Scripts/python.exe.
"""
import hashlib
import argparse
import json
import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import torch
from scipy.spatial.transform import Rotation as R

from motion import read_motion, load_dataset, clip_record, save_dataset, atomic_json

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/Locomotion'))
sys.path.insert(0, str(ROOT/'Labs/MimicKitUEFN'))
from PrepareMimicKitOmni import MJCFCharModel, JointType, serialized, matrix
from RetargetFootLift import lift_feet
from fit_motion_limits import sampled_coordinates, violation

DATASET = Path.home()/'Documents/Lafan Cutter/datasets/crawls/dataset.json'
OUT = ROOT/'Saved/LafanCrawlRetarget'
MODEL = ROOT/'Labs/MimicKitUEFN'
# Exact recovery/Stepper conversion: swap Y/Z into UE, then motion yaw -90.
# This world reflection is compensated by per-bone local frame reflections.
WORLD = np.array([[0.,0.,1.],[-1.,0.,0.],[0.,1.,0.]])
ASSET = R.from_euler('z',90,degrees=True).as_matrix()
REFERENCE_ANATOMY = np.array([[0.,0.,-1.],[1.,0.,0.],[0.,1.,0.]])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unit(v):
    return v/np.linalg.norm(v)


def basis(primary, secondary, handedness=1):
    y=unit(primary);z=unit(secondary-y*np.dot(y,secondary));x=handedness*np.cross(y,z)
    return np.column_stack((x,y,z))


def source_rotations(motion):
    result=np.empty((motion.count,len(motion.names),3,3));column=0
    for j,ch in enumerate(motion.channels):
        axes=''.join(c[0] for c in ch if c.endswith('rotation'))
        ids=[column+k for k,c in enumerate(ch) if c.endswith('rotation')]
        local=R.from_euler(axes,motion.values[:,ids],degrees=True).as_matrix() if axes else np.eye(3)
        parent=motion.parents[j];result[:,j]=local if parent<0 else result[:,parent]@local
        column+=len(ch)
    return result


def anatomical_map(motion, bones):
    """Map bone directions and axial orientation into the UEFN reference frames.

    LAFAN zero Euler is NOT a human T-pose (arm axes point up), so plain
    quaternion-name copying is invalid. Calibrate each mapped local frame using
    its child direction and a consistent anatomical forward/palm axis.
    """
    ns={n:i for i,n in enumerate(motion.names)};nt={b['name']:i for i,b in enumerate(bones)}
    refs=np.array([matrix(b['component']['position_cm']+b['component']['rotation_xyzw']) for b in bones])
    refs[:,:3,:3]=ASSET@refs[:,:3,:3];refs[:,:3,3]=refs[:,:3,3]@ASSET.T
    local=np.array([matrix(b['local']['position_cm']+b['local']['rotation_xyzw']) for b in bones])
    rotations=source_rotations(motion)
    desired={};mapping={}

    def link(target,source,target_child=None,source_child=None,kind='bone'):
        ti,si=nt[target],ns[source]
        if kind=='pelvis':
            bs=np.eye(3);bt=REFERENCE_ANATOMY
        elif kind=='foot':
            bs=basis(motion.offsets[ns[source_child]],[0,1,0])
            bt=basis(refs[nt[target_child],:3,3]-refs[ti,:3,3],[0,0,1],-1)
        elif kind=='hand':
            side=target[-1];prefix='Left' if side=='l' else 'Right'
            middle=motion.offsets[ns[prefix+'HandMiddle1']]
            across=motion.offsets[ns[prefix+'HandIndex1']]-motion.offsets[ns[prefix+'HandPinky1']]
            bs=basis(middle,across)
            middle_t=refs[nt['middle_01_'+side],:3,3]-refs[ti,:3,3]
            across_t=refs[nt['index_01_'+side],:3,3]-refs[nt['pinky_01_'+side],:3,3]
            bt=basis(middle_t,across_t,-1)
        else:
            bs=basis(motion.offsets[ns[source_child]],[0,0,1])
            bt=basis(refs[nt[target_child],:3,3]-refs[ti,:3,3],[-1,0,0],-1)
        calibration=bs@bt.T@refs[ti,:3,:3]
        desired[ti]=WORLD@rotations[:,si]@calibration
        np.testing.assert_allclose(np.linalg.det(desired[ti]),1,atol=1e-10)
        # Exact primary/secondary anatomical basis mapping, independent of pose.
        np.testing.assert_allclose(desired[ti]@refs[ti,:3,:3].T@bt,WORLD@rotations[:,si]@bs,atol=1e-10)
        mapping[target]=dict(source=source,calibration=calibration.tolist(),kind=kind)

    link('pelvis','Hips',kind='pelvis')
    # Four source spines map to five target spines; the middle source orientation
    # is shared by spine_02/03. Target lengths remain the actual asset lengths.
    spine=[('Spine','Spine1'),('Spine1','Spine2'),('Spine2','Spine3'),('Spine3','Neck')]
    for target,src in [('spine_01',0),('spine_02',1),('spine_03',1),('spine_04',2),('spine_05',3)]:
        child='neck_01' if target=='spine_05' else 'spine_'+str(int(target[-2:])+1).zfill(2)
        link(target,spine[src][0],child,spine[src][1])
    link('neck_01','Neck','neck_02','Neck1')
    link('neck_02','Neck1','head','Head')
    # Head shares the neck's up/forward convention; use its upward child axis.
    si=ns['Head'];ti=nt['head'];bs=basis(motion.offsets[ns['HeadEnd']],[0,0,1]);bt=REFERENCE_ANATOMY
    desired[ti]=WORLD@rotations[:,si]@bs@bt.T@refs[ti,:3,:3]
    mapping['head']=dict(source='Head',kind='head')
    for side,prefix in [('l','Left'),('r','Right')]:
        for t,s,tc,sc in [('clavicle','Shoulder','upperarm','Arm'),('upperarm','Arm','lowerarm','ForeArm'),
                          ('lowerarm','ForeArm','hand','Hand'),('thigh','UpLeg','calf','Leg'),('calf','Leg','foot','Foot')]:
            link(t+'_'+side,prefix+s,tc+'_'+side,prefix+sc)
        link('hand_'+side,prefix+'Hand',kind='hand')
        link('foot_'+side,prefix+'Foot','ball_'+side,prefix+'ToeBase',kind='foot')
    source_leg=np.mean([sum(np.linalg.norm(motion.offsets[ns[prefix+s]]) for s in ('Leg','Foot'))*.01 for prefix in ('Left','Right')])
    target_leg=np.mean([sum(np.linalg.norm(refs[nt[b+'_'+s],:3,3]-refs[nt[a+'_'+s],:3,3]) for a,b in [('thigh','calf'),('calf','foot')]) for s in ('l','r')])
    scale=target_leg/source_leg
    root=(motion.positions[:,ns['Hips']].astype(float)*scale)@WORLD.T
    poses=np.tile(np.eye(4),(motion.count,len(bones),1,1))
    for j,bone in enumerate(bones):
        parent=bone['parent']
        if parent>=0:poses[:,j]=poses[:,parent]@local[j]
        else:poses[:,j,:3,:3]=ASSET
        if j in desired:poses[:,j,:3,:3]=desired[j]
        if bone['name']=='pelvis':poses[:,j,:3,3]=root
    return poses,refs,local,dict(root_uniform_scale=scale,mapping=mapping,
        source_leg_length_m=source_leg,target_leg_length_m=target_leg,
        source_basis='X left, Y up, Z forward',target_basis='X forward, -Y anatomical left, Z up (same handedness conversion as Stepper/UE)',
        omitted_fingers='UEFN reference locals; no independent robotic finger articulation')


def project(model,wanted):
    count=len(wanted);names=model.get_body_names();dof=np.zeros((count,model.get_dof_size()))
    actual=np.zeros((count,len(names),3,3));actual[:,0]=wanted[:,0,:3,:3]
    local=R.from_quat(model._local_rotation.numpy()).as_matrix()
    for j in range(1,len(names)):
        parent=int(model._parent_indices[j]);joint=model.get_joint(j)
        delta=local[j].T@actual[:,parent].transpose(0,2,1)@wanted[:,j,:3,:3]
        if joint.joint_type==JointType.SPHERICAL:
            dof[:,joint.dof_idx:joint.dof_idx+3]=R.from_matrix(delta).as_rotvec();qr=delta
        elif joint.joint_type==JointType.HINGE:
            q=R.from_matrix(delta).as_quat();axis=joint.axis.numpy()
            angle=2*np.arctan2(q[:,:3]@axis,q[:,3]);angle=(angle+np.pi)%(2*np.pi)-np.pi
            dof[:,joint.dof_idx]=angle;qr=R.from_rotvec(angle[:,None]*axis).as_matrix()
        else:qr=np.eye(3)
        actual[:,j]=actual[:,parent]@local[j]@qr
    return dof,actual


def export_bvh(path,bones,poses,dt,atol=5e-6):
    # Reflect world and local axes together, exactly as the FBX/UE convention.
    poses=poses.copy();poses[:,:,:3,:3]=WORLD.T@poses[:,:,:3,:3]@np.diag([1.,-1.,1.]);poses[:,:,:3,3]=poses[:,:,:3,3]@WORLD
    locals_=poses.copy()
    for j,b in enumerate(bones):
        if b['parent']>=0:locals_[:,j]=np.linalg.inv(poses[:,b['parent']])@poses[:,j]
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',message='Gimbal lock detected')
        angles=R.from_matrix(locals_[:,:,:3,:3].reshape(-1,3,3)).as_euler('ZYX',degrees=True).reshape(len(poses),len(bones),3)
    order=[];lines=['HIERARCHY']
    def hierarchy(j,depth=0):
        pad='  '*depth;order.append(j)
        lines.extend([pad+('ROOT ' if depth==0 else 'JOINT ')+bones[j]['name'],pad+'{',pad+'  OFFSET 0 0 0',pad+'  CHANNELS 6 Xposition Yposition Zposition Zrotation Yrotation Xrotation'])
        children=[k for k,b in enumerate(bones) if b['parent']==j]
        for k in children:hierarchy(k,depth+1)
        if not children:lines.extend([pad+'  End Site',pad+'  {',pad+'    OFFSET 0 0 0',pad+'  }'])
        lines.append(pad+'}')
    hierarchy(0)
    with path.open('w',encoding='utf-8',newline='\n') as f:
        f.write('\n'.join(lines)+f'\nMOTION\nFrames: {len(poses)}\nFrame Time: {dt:.17g}\n')
        np.savetxt(f,np.concatenate((locals_[:,order][:,:,:3,3]*100,angles[:,order]),axis=-1).reshape(len(poses),-1),fmt='%.9f')
    saved=read_motion(path);idx=[saved.names.index(b['name']) for b in bones]
    error=float(np.max(np.abs(saved.positions[:,idx]-poses[:,:,:3,3])))
    # Decoded preview positions are float32. Far from the origin their ULP can
    # exceed 5 micrometres even when serialized channels preserve the exact pose.
    tolerance=max(atol,2*float(np.spacing(np.float32(np.max(np.abs(poses[:,:,:3,3]))))))
    assert error<tolerance,(error,tolerance)
    return saved,error


def main(destination_name='crawls_uefn'):
    torch.set_num_threads(1);OUT.mkdir(parents=True,exist_ok=True)
    source_hash=sha(DATASET);_,cuts=load_dataset(DATASET)
    deps=[MODEL/'humanoid_uefn.xml',MODEL/'limits.json',ROOT/'Saved/MimicKitUEFN/source-rig.json',ROOT/'Tools/Locomotion/PrepareMimicKitOmni.py',ROOT/'Tools/Locomotion/RetargetFootLift.py']
    fingerprints={str(p):sha(p) for p in deps}
    meta=json.loads((MODEL/'limits.json').read_text(encoding='utf-8'));rig=json.loads((ROOT/meta['source_rig']).read_text(encoding='utf-8'));bones=rig['skeleton'];nt={b['name']:i for i,b in enumerate(bones)}
    model=MJCFCharModel('cpu');model.load(str(MODEL/'humanoid_uefn.xml'));names=model.get_body_names()
    assert len(names)==15 and model.get_dof_size()==34
    body_ref=np.array([serialized(meta['body_frames'][n]) for n in names])
    entries=[];reports=[]
    for index,cut in enumerate(cuts):
        if cut.get('source_fbx'):
            entries.append(cut);continue
        motion=read_motion(Path(cut['source']));poses,refs,locals_ref,mapping=anatomical_map(motion,bones)
        bone_to_body=np.array([np.linalg.inv(refs[nt[meta['groups'][n]['anchor']]])@body_ref[j] for j,n in enumerate(names)])
        wanted=np.stack([poses[:,nt[meta['groups'][n]['anchor']]]@bone_to_body[j] for j,n in enumerate(names)],axis=1)
        dof,rot=project(model,wanted);root=wanted[:,0,:3,3];root_q=R.from_matrix(rot[:,0]).as_quat()
        def fk(d):
            p,q=model.forward_kinematics(torch.tensor(root,dtype=torch.float32),torch.tensor(root_q,dtype=torch.float32),model.dof_to_rot(torch.tensor(d,dtype=torch.float32)))
            return p.numpy(),q.numpy()
        before_p,before_q=fk(dof);corrections=[];unresolved=[]
        # Use the unchanged locomotion foot solver. Report infeasible candidate
        # frames explicitly; never invent a pelvis move or stretched leg.
        for tick in range(motion.count):
            previous=dof[tick].copy()
            try:
                rows=lift_feet(model,names,meta,wanted[tick:tick+1],before_p[tick:tick+1],rot[tick:tick+1],dof[tick:tick+1])
                for row in rows:row['tick']=tick
                corrections.extend(rows)
            except ValueError as e:
                dof[tick]=previous;unresolved.append(dict(frame=tick,reason=str(e)))
        p,q=fk(dof);rotations=R.from_quat(q.reshape(-1,4)).as_matrix().reshape(len(p),len(names),3,3)
        fixed=[j for j,n in enumerate(names) if not any(n.endswith('_'+a) for a in ('thigh','shin','foot'))]
        np.testing.assert_array_equal(p[:,fixed],before_p[:,fixed]);np.testing.assert_array_equal(q[:,fixed],before_q[:,fixed])
        for c in corrections:
            fi=names.index(c['side']+'_foot');t=c['tick']
            np.testing.assert_allclose(p[t,fi],c['target'],atol=2e-6)
            assert (R.from_quat(before_q[t,fi]).inv()*R.from_quat(q[t,fi])).magnitude()<3e-6
        frames=np.concatenate((root,R.from_quat(root_q).as_rotvec(),dof),axis=-1).astype(np.float32)
        assert frames.shape==(motion.count,40) and np.isfinite(frames).all()
        stem=f'{index+1:02d}_{Path(cut.get("original_source",cut["source"])).stem}_uefn'
        with (OUT/(stem+'.pkl')).open('wb') as f:pickle.dump(dict(loop_mode=0,fps=motion.fps,frames=frames),f)
        # Reconstruct the same original UEFN skeleton from the reduced anchors
        # used by the locomotion skin preview. Omitted joints retain rest locals.
        reduced=np.tile(np.eye(4),(motion.count,len(names),1,1));reduced[:,:,:3,3]=p;reduced[:,:,:3,:3]=rotations
        anchors={nt[meta['groups'][n]['anchor']]:reduced[:,j]@np.linalg.inv(bone_to_body[j]) for j,n in enumerate(names)}
        skin=np.tile(np.eye(4),(motion.count,len(bones),1,1))
        for j,b in enumerate(bones):
            if b['parent']>=0:skin[:,j]=skin[:,b['parent']]@locals_ref[j]
            else:skin[:,j,:3,:3]=ASSET
            if j in anchors:skin[:,j]=anchors[j]
        exported,roundtrip=export_bvh(OUT/(stem+'.bvh'),bones,skin,motion.dt)
        entry={**clip_record(exported,0,exported.count-1),'label':cut['label']+' · UEFN',
            'retargeted_from':cut['source'],'retarget_source_sha256':cut['source_sha256'],
            'root_uniform_scale':mapping['root_uniform_scale'],'retarget_model':'UEFN locomotion · 15 bodies / 34 DOF',
            'robot_motion':str(OUT/(stem+'.pkl'))}
        entries.append(entry)
        limit_rows=[]
        for joint in meta['joints']:
            coords,_=sampled_coordinates(model,joint,frames,1)
            limit_rows.append(dict(body=joint['body'],outside_frames=int(violation(coords,joint).sum()),frames=len(coords)))
        pos_error=np.linalg.norm(p-wanted[:,:,:3,3],axis=-1)*100
        rot_error=np.degrees(R.from_matrix((rotations.transpose(0,1,3,2)@wanted[:,:,:3,:3]).reshape(-1,3,3)).magnitude()).reshape(motion.count,-1)
        report=dict(label=cut['label'],frames=motion.count,fps=motion.fps,mapping=mapping,
            body_position_max_error_cm=dict(zip(names,pos_error.max(0).tolist())),body_orientation_max_error_deg=dict(zip(names,rot_error.max(0).tolist())),
            foot_corrections=len(corrections),maximum_foot_lift_cm=max((c['lift_cm'] for c in corrections),default=0),
            unresolved_foot_frames=unresolved,limits=limit_rows,bvh_roundtrip_error_m=roundtrip,
            original_source_sha256=cut['source_sha256'],bvh=str(exported.path),robot_motion=entry['robot_motion'])
        np.savez_compressed(OUT/(stem+'.npz'),wanted=wanted,before_position=before_p,before_quaternion=before_q,
                            position=p,quaternion=q,frames=frames,fps=motion.fps)
        atomic_json(OUT/(stem+'-report.json'),report);atomic_json(OUT/(stem+'-foot-corrections.json'),corrections)
        reports.append(report)
        print(json.dumps(dict(label=cut['label'],scale=mapping['root_uniform_scale'],foot_corrections=len(corrections),unresolved=len(unresolved),max_position_cm=float(pos_error.max()),limits=limit_rows)),flush=True)
    destination=save_dataset(DATASET.parent.parent,destination_name,entries)
    assert sha(DATASET)==source_hash
    for p,digest in fingerprints.items():assert sha(p)==digest
    for source,entry in zip(cuts,entries):
        if source.get('source_fbx'):assert sha(Path(entry['source']))==source['source_sha256']
    atomic_json(OUT/'manifest.json',dict(status='retargeted_review_candidates_not_training',dataset=str(destination),
        source_dataset=str(DATASET),source_dataset_sha256=source_hash,dependencies=fingerprints,
        target='Current locomotion 15-body/34-DOF UEFN',native_fbx_clips_unchanged=True,
        loop_mode='CLAMP',implementation_sha256=sha(Path(__file__)),motions=reports))
    print('Saved '+str(destination),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,default=DATASET)
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--name',default='crawls_uefn')
    args=parser.parse_args();DATASET=args.dataset.resolve();OUT=args.output.resolve()
    main(args.name)
