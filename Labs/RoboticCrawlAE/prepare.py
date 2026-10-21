"""Prepare only the three approved crawls, without touching their saved dataset."""
import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import torch
from scipy.spatial.transform import Rotation as R, Slerp

from features import encode, SCHEMA

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Labs/LafanCutter'))
import retarget_crawls as rt
from motion import atomic_json, load_dataset, read_motion

DATASET=Path.home()/'Documents/Lafan Cutter/datasets/crawls_uefn/dataset.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fk(model,frames):
    rootq=R.from_rotvec(frames[:,3:6]).as_quat()
    p,q=model.forward_kinematics(torch.tensor(frames[:,:3],dtype=torch.float32),torch.tensor(rootq,dtype=torch.float32),model.dof_to_rot(torch.tensor(frames[:,6:],dtype=torch.float32)))
    return p.numpy(),q.numpy()


def reduce_uefn(cut,model,meta,rig,output,stem='03_crawl'):
    motion=read_motion(Path(cut['source']));rot=rt.source_rotations(motion);names=model.get_body_names()
    reference={b['name']:rt.matrix(b['reference']['position_cm']+b['reference']['rotation_xyzw']) for b in rig['bodies']}
    asset=np.eye(4);asset[:3,:3]=rt.ASSET
    wanted=[]
    for n in names:
        anchor=meta['groups'][n]['anchor'];j=motion.names.index(anchor)
        pose=np.tile(np.eye(4),(motion.count,1,1))
        pose[:,:3,:3]=rt.WORLD@rot[:,j]@np.diag([1.,-1.,1.])
        pose[:,:3,3]=motion.positions[:,j]@rt.WORLD.T
        offset=np.linalg.inv(reference[anchor])@np.linalg.inv(asset)@rt.serialized(meta['body_frames'][n])
        wanted.append(pose@offset)
    wanted=np.stack(wanted,1);dof,actual=rt.project(model,wanted)
    root=wanted[:,0,:3,3];root_rot=R.from_matrix(actual[:,0]).as_rotvec()
    frames=np.concatenate((root,root_rot,dof),-1)
    before_p,before_q=fk(model,frames)
    corrections=rt.lift_feet(model,names,meta,wanted,before_p,actual,dof)
    frames=np.concatenate((root,root_rot,dof),-1).astype(np.float32)
    p,q=fk(model,frames)
    for row in corrections:
        t=row['tick'];j=names.index(row['side']+'_foot')
        np.testing.assert_allclose(p[t,j],row['target'],atol=2e-6)
        assert (R.from_quat(before_q[t,j]).inv()*R.from_quat(q[t,j])).magnitude()<3e-6
    with (output/f'{stem}_robotic.pkl').open('wb') as f:pickle.dump(dict(frames=frames,fps=motion.fps,loop_mode=0),f)
    atomic_json(output/f'{stem}_conversion.json',dict(source=cut['source'],source_sha256=cut['source_sha256'],
        frames=len(frames),fps=motion.fps,body_count=15,dof=34,foot_corrections=len(corrections),
        max_foot_lift_cm=max((r['lift_cm'] for r in corrections),default=0),corrections=corrections,
        method='Existing UEFN-to-robotic projection and foot correction; no LAFAN remapping'))
    return frames,motion.fps


def resample(model,frames,fps):
    """Resample generalized coordinates, then FK, preserving rigid bone lengths."""
    source=np.arange(len(frames),dtype=float)/fps
    times=np.arange(int(np.floor(source[-1]*30+1e-7))+1)/30
    result=np.empty((len(times),40),dtype=np.float64)
    for k in range(3):result[:,k]=np.interp(times,source,frames[:,k])
    result[:,3:6]=Slerp(source,R.from_rotvec(frames[:,3:6]))(times).as_rotvec()
    for i in range(1,len(model.get_body_names())):
        joint=model.get_joint(i);start=6+joint.dof_idx;width=joint.get_dof_dim()
        if width==3:result[:,start:start+3]=Slerp(source,R.from_rotvec(frames[:,start:start+3]))(times).as_rotvec()
        elif width==1:result[:,start]=np.interp(times,source,np.unwrap(frames[:,start]))
        else:raise ValueError('Unexpected joint dimension')
    p,q=fk(model,result)
    return result.astype(np.float32),p,R.from_quat(q.reshape(-1,4)).as_matrix().reshape(len(times),15,3,3).astype(np.float32),times


def preflight(p,r):
    p=torch.tensor(p[:3],dtype=torch.float64)[None];r=torch.tensor(r[:3],dtype=torch.float64)[None]
    base=encode(p,r);yaw_error=0.
    for angle in np.linspace(-np.pi,np.pi,17):
        z=torch.tensor(R.from_euler('z',angle).as_matrix(),dtype=torch.float64)
        rotated_p=(z@p.unsqueeze(-1)).squeeze(-1)+torch.tensor([13.,-7.,0.])
        delta=float((encode(rotated_p,z@r)-base).abs().max());yaw_error=max(yaw_error,delta)
    assert yaw_error<1e-10,yaw_error
    # Near-vertical forward axis exercises lateral-axis heading fallback.
    singular=r.clone();singular[:,0,0]=torch.tensor(R.from_euler('y',90,degrees=True).as_matrix())
    original=encode(p,singular)
    z=torch.tensor(R.from_euler('z',1.3).as_matrix(),dtype=torch.float64)
    singular_error=float((encode((z@p.unsqueeze(-1)).squeeze(-1),z@singular)-original).abs().max())
    assert singular_error<1e-10
    moved=p.clone();moved[:,2,:,0]+=.1
    motion_difference=float((encode(moved,r)-base).abs().max());assert motion_difference>.05
    raised=p.clone();raised[...,2]+=.2
    height_difference=float((encode(raised,r)-base).abs().max());assert height_difference>.19
    assert float((encode(raised,r,.2)-base).abs().max())<1e-10
    tilt=torch.tensor(R.from_euler('y',90,degrees=True).as_matrix(),dtype=torch.float64)
    tipped=(tilt@(p-p[:,0:1,0:1]).unsqueeze(-1)).squeeze(-1)+p[:,0:1,0:1]
    tilt_difference=float((encode(tipped,tilt@r)-base).abs().max());assert tilt_difference>.2
    differentiable=p.clone().requires_grad_(True);encode(differentiable,r).square().mean().backward()
    assert torch.isfinite(differentiable.grad).all()
    return dict(passed=True,yaw_and_xy_translation_max_error=yaw_error,vertical_heading_fallback_error=singular_error,
        pelvis_displacement_retained=motion_difference,pelvis_height_retained=height_difference,
        pitch_roll_retained=tilt_difference,finite_position_gradient=True)


def prepare(output,native_sources=None):
    torch.set_num_threads(2);output.mkdir(parents=True,exist_ok=True)
    input_hash=sha(DATASET);_,cuts=load_dataset(DATASET)
    assert len(cuts) in (3,4) and sum(bool(c.get('robot_motion')) for c in cuts)==2
    retarget=json.loads((ROOT/'Saved/LafanCrawlRetarget/manifest.json').read_text(encoding='utf-8'))
    meta=json.loads((rt.MODEL/'limits.json').read_text(encoding='utf-8'))
    rig=json.loads((ROOT/meta['source_rig']).read_text(encoding='utf-8'))
    for path,digest in retarget['dependencies'].items():
        if sha(path)==digest:continue
        # A verified limit-only update does not invalidate existing LAFAN FK.
        backup=ROOT/'Saved/MimicKitCrawl/upperbody-limits-20261017/before'
        name=Path(path).name
        assert name in ('limits.json','source-rig.json') and sha(backup/name)==digest,('Changed retarget dependency',path)
        old=json.loads((backup/'limits.json').read_text())
        for key in ('geometry','groups','body_frames','source_body_frames','parents','source_parents'):
            assert old[key]==meta[key],key
        oldrig=json.loads((backup/'source-rig.json').read_text())
        assert oldrig['bodies']==rig['bodies']
    if native_sources:
        replacements=json.loads(Path(native_sources).read_text())
        for cut in cuts:
            if cut.get('robot_motion'):continue
            entry=replacements[Path(cut['source_fbx']).stem]
            assert sha(entry['source_fbx'])==entry['source_fbx_sha256']
            assert sha(entry['source'])==entry['source_sha256']
            cut.update(entry)
    model=rt.MJCFCharModel('cpu');model.load(str(rt.MODEL/'humanoid_uefn.xml'))
    assert model.get_dof_size()==34
    arrays={};info=[];tests=[]
    for clip_id,cut in enumerate(cuts):
        if cut.get('robot_motion'):
            path=Path(cut['robot_motion']);saved=pickle.loads(path.read_bytes());frames=saved['frames'];fps=saved['fps']
            report=next(m for m in retarget['motions'] if m['robot_motion']==str(path))
            assert report['original_source_sha256']==cut['retarget_source_sha256']
        else:
            stem=f'{clip_id+1:02d}_{Path(cut["source_fbx"]).stem}'
            frames,fps=reduce_uefn(cut,model,meta,rig,output,stem);path=output/f'{stem}_robotic.pkl'
        robot,p,r,times=resample(model,frames,fps)
        tests.append(preflight(p,r))
        np.savez_compressed(output/f'clip_{clip_id}_30hz.npz',frames=robot,position=p,rotation=r,times=times)
        windows_p=np.stack([p[i:i+3] for i in range(len(p)-2)])
        windows_r=np.stack([r[i:i+3] for i in range(len(r)-2)])
        features=encode(torch.from_numpy(windows_p),torch.from_numpy(windows_r)).numpy()
        n=len(p);a=int(n*.7);b=int(n*.85)
        intervals={'train':(0,a),'validation':(a+3,b),'test':(b+3,n)}
        splits={};used=[]
        for split,(lo,hi) in intervals.items():
            indices=np.arange(lo,hi-2,dtype=np.int64);assert len(indices)>0,(clip_id,split,n)
            arrays[f'{split}_{clip_id}']=features[indices]
            arrays[f'{split}_starts_{clip_id}']=indices
            splits[split]=dict(frame_interval=[lo,hi],windows=len(indices));used.append(set(range(lo,hi)))
        assert not any(used[i]&used[j] for i in range(3) for j in range(i))
        info.append(dict(id=clip_id,label=cut['label'],source=cut['source'],source_sha256=cut['source_sha256'],
            robot_motion=str(path),robot_sha256=sha(path),original_frames=len(frames),original_fps=fps,
            frames_30hz=n,duration_s=float(times[-1]),splits=splits))
    # Equal clip weights match training sampling, rather than letting 101s dominate.
    mean=np.mean([arrays[f'train_{i}'].mean(0) for i in range(len(cuts))],axis=0)
    variance=np.mean([((arrays[f'train_{i}']-mean)**2).mean(0) for i in range(len(cuts))],axis=0)
    floors=np.tile(np.r_[np.full(3,.02),np.full(6,.05)],45).astype(np.float32)
    std=np.maximum(np.sqrt(variance),floors)
    arrays.update(mean=mean,std=std)
    np.savez_compressed(output/'features.npz',**arrays)
    assert sha(DATASET)==input_hash
    for cut in cuts:assert sha(cut['source'])==cut['source_sha256']
    manifest=dict(schema=SCHEMA,input_dim=405,body_names=model.get_body_names(),hz=30,window_poses=3,
        heading='pelvis local -X projected horizontally; +Y lateral fallback when forward projection length < 0.25',
        origin='first pelvis XY at ground height; fixed across all three poses',rotation='first two matrix columns, column-major',
        dataset=str(DATASET),dataset_sha256=input_hash,clips=info,only_user_crawl_collection=True,
        normalization='train-only equal-clip-weighted mean/std, floors 0.02m positions and 0.05 rotation components',
        sampling='equal probability per clip',
        split='70/15/15 chronological blocks within each clip; three excluded frames between blocks; no shared pose frames',
        validation_limit='Small within-source holdouts; not independent motion/subject generalization',
        target_model_hash=sha(rt.MODEL/'humanoid_uefn.xml'),limits_hash=sha(rt.MODEL/'limits.json'),
        features_sha256=sha(output/'features.npz'),native_source_overrides=str(native_sources) if native_sources else None)
    atomic_json(output/'dataset.json',manifest);atomic_json(output/'preflight.json',dict(passed=True,clips=tests))
    return manifest
