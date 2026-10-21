"""Approved retargets plus exact deployed full-body MSE targets; no NPZ conversion."""
import hashlib,json,pickle,sys,zipfile
from pathlib import Path
import numpy as np
import torch
import yaml
from scipy.spatial.transform import Rotation as R
import prepare as base
from features import encode,SCHEMA

ROOT=base.ROOT
OUT=ROOT/'Saved/RoboticMotionAE/20261019_mse_fullbody'
ARCHIVE=ROOT/'Exports/MimicKitEquipment/20261019_stopped_47039/training_source.zip'


def export_robot(model,meta,rig,frames,path,fps):
    p,q=base.shared.fk(model,frames);names=model.get_body_names();bones=rig['skeleton']
    nt={b['name']:i for i,b in enumerate(bones)};rt=base.rt
    refs=np.array([rt.matrix(b['component']['position_cm']+b['component']['rotation_xyzw']) for b in bones])
    refs[:,:3,:3]=rt.ASSET@refs[:,:3,:3];refs[:,:3,3]=refs[:,:3,3]@rt.ASSET.T
    locals_ref=np.array([rt.matrix(b['local']['position_cm']+b['local']['rotation_xyzw']) for b in bones])
    bodies=np.tile(np.eye(4),(len(p),15,1,1));bodies[...,:3,3]=p
    bodies[...,:3,:3]=R.from_quat(q.reshape(-1,4)).as_matrix().reshape(len(p),15,3,3)
    anchors={nt[meta['groups'][n]['anchor']]:bodies[:,j]@np.linalg.inv(
        np.linalg.inv(refs[nt[meta['groups'][n]['anchor']]])@rt.serialized(meta['body_frames'][n])) for j,n in enumerate(names)}
    skin=np.tile(np.eye(4),(len(p),len(bones),1,1))
    for j,b in enumerate(bones):
        if b['parent']>=0:skin[:,j]=skin[:,b['parent']]@locals_ref[j]
        else:skin[:,j,:3,:3]=rt.ASSET
        if j in anchors:skin[:,j]=anchors[j]
    motion,error=rt.export_bvh(path,bones,skin,1/fps,atol=2e-5)
    return motion,error


def main():
    torch.set_num_threads(2);OUT.mkdir(exist_ok=True)
    assert not (OUT/'verification.json').exists(),'Preparation already completed'
    source_doc=json.loads(base.DATASET.read_text(encoding='utf-8'))
    assert len(source_doc['clips'])==474
    base.atomic_json(OUT/'rejected-collection.json',source_doc)
    old=json.loads((base.OUT/'collection.json').read_text());assert base.sha(base.DATASET)==old['dataset_sha256']
    meta=json.loads((base.rt.MODEL/'limits.json').read_text());rig=json.loads((ROOT/meta['source_rig']).read_text())
    model=base.rt.MJCFCharModel('cpu');model.load(str(base.rt.MODEL/'humanoid_uefn.xml'));names=model.get_body_names()
    folder=base.DATASET.parent/'revision_20261019_mse_fullbody';folder.mkdir(exist_ok=True)
    motions=OUT/'motions';motions.mkdir(exist_ok=True)
    entries=source_doc['clips'][:12]
    assert all(c['group']=='long_reference' and c['trimmed_frames']==420 for c in entries)
    records=[];audit=[]
    for c in entries:
        records.append(dict(label=c['label'],robot_motion=c['robot_motion'],source_sha256=c['sha256'],group='retargeted_reference'))
    archive_sha=base.sha(ARCHIVE)
    receipt=json.loads(ARCHIVE.with_name('manifest.json').read_text());assert archive_sha==receipt['training_source']['sha256']
    with zipfile.ZipFile(ARCHIVE) as z:
        for name in ('humanoid_uefn.xml','limits.json','physics.json'):
            assert z.read('assets/uefn/'+name)==(base.rt.MODEL/name).read_bytes(),name
        manifest=json.loads(z.read('prepared/manifest.json'));assert manifest['body_names']==names
        rows=manifest['motions'];assert len(rows)==50
        recovery=yaml.safe_load(z.read('prepared/recovery_motions.yaml'))['motions'];assert len(recovery)==2
        selections=[(r['file'],'mse_omni' if r['gait']>=0 else 'mse_idle') for r in rows]
        selections.extend((r['file'],'mse_getup') for r in recovery)
        for file,group in selections:
            member=file.removeprefix('/workspace/mimickit_trial/');payload=z.read(member)
            path=motions/Path(member).name;path.write_bytes(payload)
            motion=pickle.loads(payload);frames=motion['frames'];fps=motion['fps']
            assert frames.shape[1]==40 and np.isfinite(frames).all()
            assert path.read_bytes()==payload
            exported,error=export_robot(model,meta,rig,frames,folder/(path.stem+'.bvh'),fps)
            c={**base.clip_record(exported,0,exported.count-1),'label':path.stem+' · MSE target',
               'robot_motion':str(path),'group':group,'file':folder.name+'/'+exported.path.name,
               'sha256':exported.sha256,'retarget_model':'Exact deployed full-body MSE target',
               'training_archive_member':member,'robot_sha256':base.sha(path)}
            entries.append(c);records.append(dict(label=c['label'],robot_motion=str(path),source_sha256=c['sha256'],group=group))
            audit.append(dict(label=path.stem,group=group,archive_member=member,sha256=base.sha(path),byte_identical=True,
                newly_added_foot_displacement_m=0.,bvh_roundtrip_error_m=error,frames=len(frames),fps=fps))
    assert len(entries)==64
    doc={**source_doc,'clips':entries,'name':'loco_uefn','selection':'12 trimmed retargets plus exact deployed 48 omni,2 idle,2 get-up targets'}
    base.atomic_json(base.DATASET,doc)
    base.atomic_json(OUT/'collection.json',dict(dataset=str(base.DATASET),dataset_sha256=base.sha(base.DATASET),
        clips=64,retargeted_clips=12,mse_clips=52,native=audit,training_source_sha256=archive_sha,
        training_source=str(ARCHIVE),model_sha256=base.sha(base.rt.MODEL/'humanoid_uefn.xml'),
        note='No new projection, IK, foot correction, limit clamping or upper-body freezing applied to MSE targets',
        duration_seconds=sum((c['frames']-1)/c['fps'] for c in entries)))
    data=OUT/'data';data.mkdir();arrays={};info=[];checks=[];upper=[]
    for i,record in enumerate(records):
        saved=pickle.loads(Path(record['robot_motion']).read_bytes());robot,p,r,times=base.shared.resample(model,saved['frames'],saved['fps'])
        checks.append(base.shared.preflight(p,r))
        np.savez_compressed(data/f'clip_{i}_30hz.npz',frames=robot,position=p,rotation=r)
        idx=np.arange(len(p)-2)[:,None]+np.arange(3)[None,:]
        features=encode(torch.from_numpy(p[idx]),torch.from_numpy(r[idx])).numpy()
        n=len(p);hold=max(3,int(n*.2));a=n-2*hold-4;b=a+2+hold;assert a>=3,(i,n)
        splits={};used=[]
        for name,(lo,hi) in dict(train=(0,a),validation=(a+2,b),test=(b+2,n)).items():
            starts=np.arange(lo,hi-2,dtype=np.int64);assert len(starts)>0
            pose_ids=set((starts[:,None]+np.arange(3)[None,:]).ravel());assert not any(pose_ids&s for s in used);used.append(pose_ids)
            arrays[f'{name}_{i}']=features[starts];arrays[f'{name}_starts_{i}']=starts
            splits[name]=dict(frame_interval=[lo,hi],windows=len(starts))
        relatives=r[:,0].transpose(0,2,1)[:,None]@r
        angles=np.rad2deg(R.from_matrix((relatives[0].transpose(0,2,1)[None]@relatives).reshape(-1,3,3)).magnitude()).reshape(len(p),15)
        upper_row={name:float(angles[:,names.index(name)].max()) for name in names[1:9]}
        upper.append(dict(id=i,label=record['label'],pelvis_relative_rotation_excursion_deg=upper_row))
        assert max(upper_row.values())>.01,('Frozen upper body',record['label'])
        # Both arms must articulate in moving accepted locomotion, excluding idles.
        if record['group']=='mse_omni':
            assert min(upper_row['left_upper_arm'],upper_row['right_upper_arm'])>1.,upper_row
        info.append(dict(id=i,**record,robot_sha256=base.sha(record['robot_motion']),frames_30hz=n,splits=splits))
        if i%10==0:print(json.dumps(dict(stage='features',clip=i,frames=n)),flush=True)
    # Equal families: long diverse references and exact MSE motions. Uniform clips
    # within each family prevents the few long captures/10s idle swallowing loops.
    weights=np.array([.5/12 if i<12 else .5/52 for i in range(64)],dtype=np.float64)
    mean=sum(weights[i]*arrays[f'train_{i}'].mean(0,dtype=np.float64) for i in range(64))
    variance=sum(weights[i]*((arrays[f'train_{i}']-mean)**2).mean(0) for i in range(64))
    floors=np.tile(np.r_[np.full(3,.02),np.full(6,.05)],45)
    arrays.update(mean=mean.astype(np.float32),std=np.maximum(np.sqrt(variance),floors).astype(np.float32),clip_weights=weights.astype(np.float32))
    np.savez_compressed(data/'features.npz',**arrays)
    spec=dict(schema=SCHEMA,input_dim=405,body_names=names,hz=30,window_poses=3,clips=info,
        sampling='50% retargeted references,50% exact MSE targets; uniform clips then windows within each family',
        normalization='training-only mean/std with same clip weights as sampling; floors .02m/.05 rotation',
        split='Chronological roughly60/20/20, two-frame gaps; short clips reserve >=3 poses per holdout; no shared pose frames',
        validation_limit='Within-motion holdouts; shortest loops have only one held-out window. Not independent-motion generalization',
        features_sha256=base.sha(data/'features.npz'),dataset_sha256=base.sha(base.DATASET),model_sha256=base.sha(base.rt.MODEL/'humanoid_uefn.xml'))
    base.atomic_json(data/'dataset.json',spec);base.atomic_json(data/'preflight.json',dict(passed=True,clips=checks))
    base.atomic_json(OUT/'verification.json',dict(passed=True,clips=64,exact_mse_targets=52,source_archive_sha256=archive_sha,
        all_mse_targets_byte_identical=True,added_foot_displacement_m=0.,upper_body_motion=upper,
        no_transition_imports=True,model_identical_to_deployment=True,disjoint_pose_frames=True))
    print(json.dumps(dict(stage='ready',clips=64)),flush=True)


if __name__=='__main__':main()
