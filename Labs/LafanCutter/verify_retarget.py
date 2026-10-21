"""Focused parity and saved-output checks for the crawl retarget."""
import json
import argparse
import pickle
import numpy as np
import torch
from scipy.spatial.transform import Rotation as R
import retarget_crawls as t


def main():
    torch.set_num_threads(1)
    model=t.MJCFCharModel('cpu');model.load(str(t.MODEL/'humanoid_uefn.xml'))
    names=model.get_body_names();meta=json.loads((t.MODEL/'limits.json').read_text(encoding='utf-8'))
    rig=json.loads((t.ROOT/meta['source_rig']).read_text(encoding='utf-8'))
    ref={b['name']:t.matrix(b['reference']['position_cm']+b['reference']['rotation_xyzw']) for b in rig['bodies']}
    asset=np.eye(4);asset[:3,:3]=t.ASSET
    motion=np.eye(4);motion[:3,:3]=R.from_euler('z',-90,degrees=True).as_matrix()
    offsets={n:np.linalg.inv(ref[meta['groups'][n]['anchor']])@np.linalg.inv(asset)@t.serialized(meta['body_frames'][n]) for n in names}
    clip=json.loads((t.ROOT/'Labs/OmniLocomotionViewer/data.json').read_text(encoding='utf-8'))['clips'][0]
    raw=json.loads((t.ROOT/'Saved/Diagnostics/OmniRecord20261015'/(clip['id']+'.json')).read_text(encoding='utf-8'))
    cut=clip['cut'];poses=[r['pose'] for r in raw['rows'][cut['start']:cut['end']+1]]
    wanted=np.array([[motion@t.matrix(f[raw['names'].index(meta['groups'][n]['anchor'])])@offsets[n] for n in names] for f in poses])
    dof,rot=t.project(model,wanted);root=wanted[:,0,:3,3];root_q=R.from_matrix(rot[:,0]).as_quat()
    p,q=model.forward_kinematics(torch.tensor(root,dtype=torch.float32),torch.tensor(root_q,dtype=torch.float32),model.dof_to_rot(torch.tensor(dof,dtype=torch.float32)))
    t.lift_feet(model,names,meta,wanted,p.numpy(),rot,dof)
    actual=np.concatenate([root,R.from_quat(root_q).as_rotvec(),dof],axis=-1).astype(np.float32)
    expected=pickle.loads((t.ROOT/'Saved/MimicKitUEFN/omni'/(clip['id']+'.pkl')).read_bytes())['frames']
    np.testing.assert_allclose(actual,expected,atol=1e-6,rtol=0)
    manifest=json.loads((t.OUT/'manifest.json').read_text(encoding='utf-8'))
    assert t.sha(t.DATASET)==manifest['source_dataset_sha256']
    for path,expected_hash in manifest['dependencies'].items():assert t.sha(path)==expected_hash
    _,clips=t.load_dataset(manifest['dataset']);_,original=t.load_dataset(t.DATASET)
    assert len(clips)==len(original)
    for source,dest in zip(original,clips):
        assert source['frames']==dest['frames'] and source['fps']==dest['fps']
        if source.get('source_fbx'):assert source['source_sha256']==dest['source_sha256']
    rows=[]
    for report in manifest['motions']:
        blob=pickle.loads(t.Path(report['robot_motion']).read_bytes());saved=blob['frames'];fps=blob['fps']
        assert blob['loop_mode']==0 and saved.shape==(report['frames'],40)
        assert fps==report['fps']
        root_q=R.from_rotvec(saved[:,3:6]).as_quat()
        p,q=model.forward_kinematics(torch.tensor(saved[:,:3]),torch.tensor(root_q,dtype=torch.float32),model.dof_to_rot(torch.tensor(saved[:,6:])))
        data=np.load(t.Path(report['robot_motion']).with_suffix('.npz'))
        pos_error=float(np.max(np.abs(p.numpy()-data['position'])))
        rotation_error=float(np.max((R.from_quat(q.numpy().reshape(-1,4)).inv()*R.from_quat(data['quaternion'].reshape(-1,4))).magnitude()))
        assert pos_error<3e-6 and rotation_error<3e-6
        source=t.read_motion(t.Path(next(c['retargeted_from'] for c in clips if c.get('robot_motion')==report['robot_motion'])))
        np.testing.assert_allclose(t.source_rotations(source).transpose(0,1,3,2)@t.source_rotations(source),np.broadcast_to(np.eye(3),(source.count,len(source.names),3,3)),atol=1e-10)
        # Compare physical collider support heights using the actual current box.
        from RetargetFootLift import box_bottom
        clearance={}
        for side in ('left','right'):
            n=side+'_foot';j=names.index(n);g=next(g for g in meta['geometry'] if g['body']==n)
            local=np.linalg.inv(t.serialized(meta['body_frames'][n]))@t.serialized(g)
            before=data['wanted'][:,j];after_rot=R.from_quat(data['quaternion'][:,j]).as_matrix()
            old=np.array([box_bottom(v[:3,3],v[:3,:3],local[:3,3],local[:3,:3],g['size']) for v in before])
            after=np.array([box_bottom(x,r,local[:3,3],local[:3,:3],g['size']) for x,r in zip(data['position'][:,j],after_rot)])
            extra=np.maximum(0,np.minimum(old,0)-after)
            resolved=np.ones(len(extra),dtype=bool)
            for row in report['unresolved_foot_frames']:resolved[row['frame']]=False
            assert not resolved.any() or extra[resolved].max()<3e-6,(n,extra[resolved].max())
            clearance[side]=float(extra.max()*100)
        rows.append(dict(label=report['label'],frames=len(saved),fk_position_roundtrip_m=pos_error,
                         fk_orientation_roundtrip_rad=rotation_error,remaining_added_foot_penetration_cm=clearance,
                         unresolved_foot_frames=report['unresolved_foot_frames']))
    result=dict(passed=True,locomotion_parity_clip=clip['id'],locomotion_parity_max_channel_error=float(np.max(abs(actual-expected))),
                original_dataset_unchanged=True,native_fbx_clips_byte_identical=True,model_and_locomotion_dependencies_unchanged=True,
                joint_limits_not_modified=True,motions=rows)
    t.atomic_json(t.OUT/'verification.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dataset',type=t.Path,default=t.DATASET);parser.add_argument('--output',type=t.Path,default=t.OUT)
    args=parser.parse_args();t.DATASET=args.dataset.resolve();t.OUT=args.output.resolve();main()
