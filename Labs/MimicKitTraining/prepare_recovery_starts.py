"""Retarget the user's current recovery FBXs for review; no training changes."""
import argparse, hashlib, json, pickle, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path.home()/'Documents/Cursor/stepper/ue5/slashes/recoveries'
OUT = ROOT/'Saved/MimicKitEquipment/recovery-preview'
NAMES = ('getUp_front_quick', 'getUp_back_quick')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert():
    sys.path.insert(0, str(ROOT/'Labs/LafanCutter'))
    from import_fbx import convert as convert_fbx
    OUT.mkdir(parents=True, exist_ok=True)
    receipts = []
    for name in NAMES:
        source = SOURCE/(name+'.fbx')
        before = sha(source)
        destination = OUT/(name+'.fbx')
        shutil.copy2(source, destination)
        receipt = convert_fbx(destination, OUT/(name+'.bvh'))
        assert before == sha(source) == sha(destination)
        receipt.update(original_source=str(source), modified_unix=source.stat().st_mtime)
        receipts.append(receipt)
    (OUT/'imports.json').write_text(json.dumps(receipts, indent=2))
    print(json.dumps(receipts, indent=2))


def prepare():
    import numpy as np
    import torch
    from scipy.spatial.transform import Rotation as R
    sys.path.insert(0, str(ROOT/'Labs/RoboticCrawlAE'))
    import prepare as ae
    from fit_motion_limits import sampled_coordinates, violation
    sys.path.insert(0, str(ROOT/'Labs/CrawlTraining'))
    from repair_references import wanted_poses
    from RetargetFootLift import box_bottom
    torch.set_num_threads(1)
    meta = json.loads((ROOT/'Labs/MimicKitUEFN/limits.json').read_text())
    rig = json.loads((ROOT/meta['source_rig']).read_text())
    model = ae.rt.MJCFCharModel('cpu')
    model.load(str(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml'))
    # Same shapes and local geometry as the established PHAT comparison viewer.
    robot_bodies = json.loads((ROOT/'Saved/MimicKitCrawl/upperarm-pose-audit/data.json').read_text())['bodies']
    assert [b['name'] for b in robot_bodies] == model.get_body_names()
    authored_bodies = []
    for body in rig['bodies']:
        shapes = []
        for s in body['shapes']:
            size = ([s['radius_cm']*.01, s['cylinder_length_cm']*.005] if s['kind']=='capsule'
                    else [s['radius_cm']*.01] if s['kind']=='sphere'
                    else (np.array(s['half_extent_cm'])*.01).tolist())
            quat = s['local']['rotation_xyzw']
            shapes.append(dict(type=s['kind'],size=size,pos=(np.array(s['local']['position_cm'])*.01).tolist(),quat=[quat[3],*quat[:3]]))
        authored_bodies.append(dict(name=body['name'],shapes=shapes))
    clips = []
    for receipt in json.loads((OUT/'imports.json').read_text()):
        source = Path(receipt['original_source'])
        assert sha(source) == receipt['source_fbx_sha256'], 'FBX changed; reconvert latest file'
        name = source.stem
        bvh = OUT/(name+'.bvh')
        motion = ae.read_motion(bvh)
        wanted = wanted_poses(bvh,model,meta,rig)
        dof,actual = ae.rt.project(model,wanted)
        frames=np.concatenate((wanted[:,0,:3,3],R.from_matrix(actual[:,0]).as_rotvec(),dof),-1)
        before_p,before_q=ae.fk(model,frames)
        corrections=[];unreachable=[]
        candidate=dof.copy()
        for tick in range(len(frames)):
            trial=dof[tick:tick+1].copy()
            try:
                rows=ae.rt.lift_feet(model,model.get_body_names(),meta,wanted[tick:tick+1],before_p[tick:tick+1],actual[tick:tick+1],trial)
                candidate[tick]=trial[0]
                corrections.extend([dict(row,tick=tick) for row in rows])
            except ValueError as e:
                unreachable.append(dict(frame=tick,error=str(e)))
        # Review the unmodified projection if this clip cannot use the existing
        # correction throughout. Never silently stretch a leg or shift its hip.
        if not unreachable:frames[:,6:]=candidate
        frames=frames.astype(np.float32);fps=motion.fps
        (OUT/(name+'_robotic.pkl')).write_bytes(pickle.dumps(dict(frames=frames,fps=fps,loop_mode=0)))
        clearance=[]
        for side in ('right','left'):
            fi=model.get_body_names().index(side+'_foot')
            rest=meta['body_frames'][side+'_foot'];rr=R.from_quat(rest['quaternion']).as_matrix()
            g=next(g for g in meta['geometry'] if g['body']==side+'_foot')
            gp=rr.T@(np.array(g['position'])-rest['position']);gr=rr.T@R.from_quat(g['quaternion']).as_matrix()
            old=np.array([box_bottom(w[:3,3],w[:3,:3],gp,gr,np.array(g['size'])) for w in wanted[:,fi]])
            raw=np.array([box_bottom(p[fi],r[fi],gp,gr,np.array(g['size'])) for p,r in zip(before_p,actual)])
            clearance.append(dict(side=side,max_original_penetration_cm=float(max(0,-old.min())*100),max_projected_penetration_cm=float(max(0,-raw.min())*100),max_added_penetration_cm=float(np.maximum(0,np.minimum(old,0)-raw).max()*100)))
        rot = ae.rt.WORLD @ ae.rt.source_rotations(motion) @ np.diag([1.,-1.,1.])
        pos = motion.positions @ ae.rt.WORLD.T
        source_pose = np.stack([np.concatenate((pos[:,motion.names.index(b['name'])],R.from_matrix(rot[:,motion.names.index(b['name'])]).as_quat()),-1) for b in rig['bodies']],1)
        pp, qq = ae.fk(model,frames)
        robot_pose = np.concatenate((pp,qq),-1)
        # One fixed XY origin per clip; retain authored translation and height.
        origin = robot_pose[0,0,:2].copy()
        robot_pose[:,:,:2] -= origin
        source_pose[:,:,:2] -= origin
        limits=[]
        for joint in meta['joints']:
            values,_=sampled_coordinates(model,joint,frames,16)
            bad=violation(values,joint)
            if bad.any():limits.append(dict(body=joint['body'],outside=int(bad.sum()),samples=len(bad)))
        clips.append(dict(id=name,label='Get up · '+('front' if 'front' in name else 'back'),fps=fps,frames=len(frames),seconds=(len(frames)-1)/fps,
            source_sha256=receipt['source_fbx_sha256'],modified_unix=receipt['modified_unix'],limit_exceedances=limits,
            foot_lift_applied=not unreachable,foot_lift_unreachable=unreachable,foot_clearance=clearance,
            foot_lift_frames=len(corrections) if not unreachable else 0,max_foot_lift_cm=max((r['lift_cm'] for r in corrections),default=0.) if not unreachable else 0.,
            poses=robot_pose.round(7).tolist(),source_poses=source_pose.round(7).tolist()))
    data=dict(bodies=robot_bodies,source_bodies=authored_bodies,clips=clips,phat_source_files=meta['source_files'],
        method='Existing native UEFN anchor projection. Independent foot lift only if the whole clip is reachable; otherwise pure projection for review. No limit clamp, seam fit or motion rescaling.')
    (OUT/'data.json').write_text(json.dumps(data,separators=(',',':')))
    report=dict(data);report['clips']=[{k:v for k,v in c.items() if k not in ('poses','source_poses')} for c in clips]
    (OUT/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report['clips'],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('convert','prepare'));args=parser.parse_args()
    (convert if args.stage=='convert' else prepare)()
