"""Build the user's combined robotic motion collection and isolated AE features."""
import hashlib, json, math, pickle, sys
from pathlib import Path
import numpy as np
import torch
from scipy.spatial.transform import Rotation as R
from features import encode, SCHEMA

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Labs/LafanCutter'))
import retarget_crawls as rt
from motion import atomic_json, load_dataset, read_motion, write_cut, clip_record, save_dataset
# Reuse the tested generalized-coordinate interpolation and feature invariants.
import importlib.util
spec=importlib.util.spec_from_file_location('crawl_preparation',ROOT/'Labs/RoboticCrawlAE/prepare.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
sha=shared.sha
OUT=ROOT/'Saved/RoboticMotionAE/20261019_loco'
DATASET=Path.home()/'Documents/Lafan Cutter/datasets/loco_uefn/dataset.json'
NATIVE=Path.home()/'Documents/Cursor/stepper/ue5'
FOLDERS=['animation_run_omni_only/npz_final','animation_run_transition_only/npz_final_trimmed',
         'animations_omni_only/npz_final','animation_transitions_only_full/npz_final_trimmed']


def native_motion(path, model, meta, rig, output):
    """Same model-space matrices consumed by the existing Run/Walk IK loader."""
    with np.load(path,allow_pickle=False) as data:
        names=data['bone_names'].tolist();fps=float(data['fps'])
        poses=data['model_global_matrix'].astype(np.float64).swapaxes(-1,-2)
        np.testing.assert_allclose(poses[...,:3,3],data['model_global_joint_pos_m'],atol=2e-6)
        assert int(data['axis_up_axis'])==2 and bool(data['model_reconstructable'])
    # Row-vector Y-up metres -> column-vector physical world/body conventions.
    poses[...,:3,:3]=rt.WORLD@poses[...,:3,:3]@np.diag([1.,-1.,1.])
    poses[...,:3,3]=poses[...,:3,3]@rt.WORLD.T
    reference={b['name']:rt.matrix(b['reference']['position_cm']+b['reference']['rotation_xyzw']) for b in rig['bodies']}
    asset=np.eye(4);asset[:3,:3]=rt.ASSET
    body_names=model.get_body_names()
    wanted=np.stack([poses[:,names.index(meta['groups'][n]['anchor'])]@
        (np.linalg.inv(reference[meta['groups'][n]['anchor']])@np.linalg.inv(asset)@rt.serialized(meta['body_frames'][n])) for n in body_names],1)
    dof,rot=rt.project(model,wanted)
    root=wanted[:,0,:3,3];rootrot=R.from_matrix(rot[:,0]).as_rotvec()
    frames=np.concatenate((root,rootrot,dof),-1)
    before_p,before_q=shared.fk(model,frames)
    corrections=rt.lift_feet(model,body_names,meta,wanted,before_p,rot,dof)
    frames=np.concatenate((root,rootrot,dof),-1).astype(np.float32)
    p,q=shared.fk(model,frames)
    for row in corrections:
        t=row['tick'];j=body_names.index(row['side']+'_foot')
        np.testing.assert_allclose(p[t,j],row['target'],atol=3e-6,rtol=2e-7)
        assert (R.from_quat(before_q[t,j]).inv()*R.from_quat(q[t,j])).magnitude()<4e-6
    fixed=[i for i,n in enumerate(body_names) if not any(n.endswith('_'+s) for s in ('thigh','shin','foot'))]
    np.testing.assert_allclose(before_p[:,fixed],p[:,fixed],atol=2e-6,rtol=2e-7)
    # Reconstruct full UEFN preview from the actual physical anchors.
    bones=rig['skeleton'];nt={b['name']:i for i,b in enumerate(bones)}
    refs=np.array([rt.matrix(b['component']['position_cm']+b['component']['rotation_xyzw']) for b in bones])
    refs[:,:3,:3]=rt.ASSET@refs[:,:3,:3];refs[:,:3,3]=refs[:,:3,3]@rt.ASSET.T
    locals_ref=np.array([rt.matrix(b['local']['position_cm']+b['local']['rotation_xyzw']) for b in bones])
    reduced=np.tile(np.eye(4),(len(p),len(body_names),1,1));reduced[...,:3,3]=p
    reduced[...,:3,:3]=R.from_quat(q.reshape(-1,4)).as_matrix().reshape(len(p),15,3,3)
    anchors={nt[meta['groups'][n]['anchor']]:reduced[:,j]@np.linalg.inv(
        np.linalg.inv(refs[nt[meta['groups'][n]['anchor']]])@rt.serialized(meta['body_frames'][n])) for j,n in enumerate(body_names)}
    skin=np.tile(np.eye(4),(len(p),len(bones),1,1))
    for j,b in enumerate(bones):
        if b['parent']>=0:skin[:,j]=skin[:,b['parent']]@locals_ref[j]
        else:skin[:,j,:3,:3]=rt.ASSET
        if j in anchors:skin[:,j]=anchors[j]
    bvh,error=rt.export_bvh(output.with_suffix('.bvh'),bones,skin,1/fps)
    with output.with_suffix('.pkl').open('wb') as f:pickle.dump(dict(frames=frames,fps=fps,loop_mode=0),f)
    report=dict(source=str(path),source_sha256=sha(path),source_contract='model_global_matrix: row-vector Y-up metres; same as IK MotionClip',
        frames=len(frames),fps=fps,foot_corrections=len(corrections),max_lift_cm=max((c['lift_cm'] for c in corrections),default=0.),
        position_max_error_cm=float(np.linalg.norm(p-wanted[...,:3,3],axis=-1).max()*100),bvh_roundtrip_error_m=error,
        no_joint_limit_clamping=True)
    atomic_json(output.with_suffix('.json'),report)
    entry={**clip_record(bvh,0,bvh.count-1),'label':path.stem+' · UEFN',
        'robot_motion':str(output.with_suffix('.pkl')),'native_npz':str(path),'native_sha256':sha(path),
        'retarget_model':'UEFN locomotion · 15 bodies / 34 DOF','group':path.parent.parent.name}
    return entry,report


def prepare_collection():
    torch.set_num_threads(2)
    OUT.mkdir(parents=True,exist_ok=True)
    result=OUT/'collection.json'
    if result.exists():
        saved=json.loads(result.read_text());assert sha(DATASET)==saved['dataset_sha256'];return saved
    if (OUT/'dataset-before.json').exists():
        assert sha(OUT/'dataset-before.json')==sha(DATASET),'Dataset changed during preparation'
    else:(OUT/'dataset-before.json').write_bytes(DATASET.read_bytes())
    _,cuts=load_dataset(DATASET);assert len(cuts)==12
    sys.path.insert(0,str(ROOT/'Labs/CrawlTraining'))
    from current_phat import current_source
    meta=current_source();rig=json.loads((ROOT/meta['source_rig']).read_text())
    model=rt.MJCFCharModel('cpu');model.load(str(rt.MODEL/'humanoid_uefn.xml'))
    motions=OUT/'motions';motions.mkdir(exist_ok=True)
    entries=[];reports=[]
    for i,cut in enumerate(cuts):
        motion=read_motion(Path(cut['source']),decode=False)
        start=math.ceil(7/motion.dt-1e-8);assert start==420 and start<motion.count
        robot=pickle.loads(Path(cut['robot_motion']).read_bytes());assert len(robot['frames'])==motion.count
        robot['frames']=robot['frames'][start:].copy();stem=motions/f'{i:03d}_reference'
        with stem.with_suffix('.pkl').open('wb') as f:pickle.dump(robot,f)
        overlay=read_motion(Path(cut['retargeted_from']),decode=False)
        assert overlay.count==motion.count and overlay.sha256==cut['retarget_source_sha256']
        overlay_path=stem.with_name(stem.name+'_source.bvh');write_cut(overlay,overlay_path,start,overlay.count-1)
        entries.append({**cut,'start':start,'end':motion.count-1,'frames':motion.count-start,
            'label':cut['label']+' · lead-in removed','robot_motion':str(stem.with_suffix('.pkl')),
            'retargeted_from':str(overlay_path),'retarget_source_sha256':sha(overlay_path),
            'group':'long_reference','trimmed_seconds':start*motion.dt,'trimmed_frames':start})
        reports.append(dict(label=cut['label'],removed_frames=start,removed_seconds=start*motion.dt,remaining_frames=len(robot['frames'])))
        print(json.dumps(dict(stage='trimmed',clip=i,remaining_frames=len(robot['frames']))),flush=True)
    native_reports=[]
    for folder in FOLDERS:
        for path in sorted((NATIVE/folder).glob('*.npz')):
            entry,report=native_motion(path,model,meta,rig,motions/f'{len(entries):03d}_{path.stem}')
            entries.append(entry);native_reports.append(report)
            if len(entries)%25==0:print(json.dumps(dict(stage='native_projection',clips=len(entries))),flush=True)
    assert len(native_reports)==462 and len(entries)==474
    # Publish only after every source converted and all foot correction checks passed.
    dataset=save_dataset(DATASET.parent.parent,'loco_uefn',entries)
    saved=dict(dataset=str(dataset),dataset_sha256=sha(dataset),clips=len(entries),native_clips=len(native_reports),
        trimmed=reports,native=native_reports,body_names=model.get_body_names(),model_sha256=sha(rt.MODEL/'humanoid_uefn.xml'),
        duration_seconds=sum((e['frames']-1)/e['fps'] for e in entries),
        note='Native clips preserved in full; physical reduction with established foot correction; no limit clamp or PHAT edit')
    atomic_json(result,saved);return saved


def prepare_features():
    collection=prepare_collection();out=OUT/'data';out.mkdir(exist_ok=True)
    if (out/'dataset.json').exists():
        old=json.loads((out/'dataset.json').read_text());assert sha(out/'features.npz')==old['features_sha256'];return
    _,clips=load_dataset(DATASET)
    model=rt.MJCFCharModel('cpu');model.load(str(rt.MODEL/'humanoid_uefn.xml'))
    arrays={};info=[];checks=[]
    for i,cut in enumerate(clips):
        path=Path(cut['robot_motion']);saved=pickle.loads(path.read_bytes())
        robot,p,r,times=shared.resample(model,saved['frames'],saved['fps'])
        checks.append(shared.preflight(p,r))
        np.savez_compressed(out/f'clip_{i}_30hz.npz',frames=robot,position=p,rotation=r)
        idx=np.arange(len(p)-2)[:,None]+np.arange(3)[None,:]
        features=encode(torch.from_numpy(p[idx]),torch.from_numpy(r[idx])).numpy()
        n=len(p);a=int(n*.6);b=int(n*.8)
        splits={}
        for name,(lo,hi) in dict(train=(0,a),validation=(a+2,b),test=(b+2,n)).items():
            starts=np.arange(lo,hi-2,dtype=np.int64);assert len(starts)>0,(i,n,name)
            arrays[f'{name}_{i}']=features[starts];arrays[f'{name}_starts_{i}']=starts
            splits[name]=dict(frame_interval=[lo,hi],windows=len(starts))
        info.append(dict(id=i,label=cut['label'],group=cut['group'],robot_motion=str(path),robot_sha256=sha(path),frames_30hz=n,
            source_sha256=cut['source_sha256'],splits=splits))
        if i%50==0:print(json.dumps(dict(stage='features',clip=i,frames=n)),flush=True)
    train=np.concatenate([arrays[f'train_{i}'] for i in range(len(clips))])
    mean=train.mean(0,dtype=np.float64).astype(np.float32)
    std=train.std(0,dtype=np.float64).astype(np.float32)
    floors=np.tile(np.r_[np.full(3,.02),np.full(6,.05)],45).astype(np.float32)
    arrays.update(mean=mean,std=np.maximum(std,floors));np.savez_compressed(out/'features.npz',**arrays)
    manifest=dict(schema=SCHEMA,input_dim=405,body_names=model.get_body_names(),hz=30,window_poses=3,clips=info,
        normalization='train-only mean/std across valid windows; position floor .02m, rotation floor .05',
        sampling='uniform over training windows; clip contribution proportional to retained duration',
        split='60/20/20 chronological per clip; two additional excluded pose frames at each boundary; no cross-clip/seam windows',
        validation_limit='Within-motion holdouts, often short or periodic; not independent subject or motion generalization',
        dataset_sha256=collection['dataset_sha256'],features_sha256=sha(out/'features.npz'),model_sha256=collection['model_sha256'])
    atomic_json(out/'dataset.json',manifest);atomic_json(out/'preflight.json',dict(passed=True,clips=checks))
    print(json.dumps(dict(stage='prepared',clips=len(clips),train_windows=len(train))),flush=True)


if __name__=='__main__':prepare_features()
