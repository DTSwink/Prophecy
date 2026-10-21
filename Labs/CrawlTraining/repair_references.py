"""Build corrected policy-only crawl/idle candidates; preserve AE and originals."""
from pathlib import Path
import sys, json, pickle, hashlib
import numpy as np
from scipy.spatial.transform import Rotation as R
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Labs/RoboticCrawlAE'))
import prepare as ae
from idle_contact import fit_idle
from crawl_contact import fit_crawl


def wanted_poses(source, model, meta, rig):
    rt = ae.rt; motion = ae.read_motion(Path(source)); rotations = rt.source_rotations(motion)
    reference = {b['name']: rt.matrix(b['reference']['position_cm']+b['reference']['rotation_xyzw']) for b in rig['bodies']}
    asset = np.eye(4); asset[:3,:3] = rt.ASSET
    wanted = []
    for name in model.get_body_names():
        anchor = meta['groups'][name]['anchor']; j = motion.names.index(anchor)
        pose = np.tile(np.eye(4),(motion.count,1,1))
        pose[:,:3,:3] = rt.WORLD@rotations[:,j]@np.diag([1.,-1.,1.])
        pose[:,:3,3] = motion.positions[:,j]@rt.WORLD.T
        offset = np.linalg.inv(reference[anchor])@np.linalg.inv(asset)@rt.serialized(meta['body_frames'][name])
        wanted.append(pose@offset)
    return np.stack(wanted,1)


def close_crawl_cycle(model, frames, tail_frames=8):
    """Close the small authored cycle mismatch in a policy-only copy.

    Keep the complete clip and root XY travel. Ease the final eight frames to
    the opening articulation/height, with zero correction slope at both ends.
    """
    f = np.array(frames, dtype=float, copy=True)
    u = np.linspace(0., 1., tail_frames); blend = u*u*(3.-2.*u)
    changes = []
    channels = [(3, 3)]
    for j in range(1, model.get_num_joints()):
        joint = model.get_joint(j); channels.append((6+joint.dof_idx,joint.get_dof_dim()))
    for start, width in channels:
        if width == 3:
            first = R.from_rotvec(f[0,start:start+3]); last = R.from_rotvec(f[-1,start:start+3])
            delta = (last.inv()*first).as_rotvec()
            f[-tail_frames:,start:start+3] = (R.from_rotvec(f[-tail_frames:,start:start+3])
                * R.from_rotvec(blend[:,None]*delta)).as_rotvec()
            changes.append(float(np.linalg.norm(delta)))
        else:
            delta = (f[0,start]-f[-1,start]+np.pi)%(2*np.pi)-np.pi
            f[-tail_frames:,start] += blend*delta; changes.append(float(abs(delta)))
    dz = float(f[0,2]-f[-1,2]); f[-tail_frames:,2] += blend*dz
    np.testing.assert_array_equal(f[:,:2],frames[:,:2])
    return f.astype(np.float32),dict(tail_frames=tail_frames,max_local_rotation_correction_deg=float(np.rad2deg(max(changes))),
                                    root_height_correction_m=dz,root_xy_preserved=True)


def main():
    out = ROOT/'Saved/MimicKitCrawl/corrected-references'; out.mkdir(exist_ok=True)
    pointer = json.loads((ROOT/'Saved/RoboticCrawlAE/current-run.json').read_text(encoding='utf-8-sig'))
    run = Path(pointer['run']); manifest = json.loads((run/'data/dataset.json').read_text())
    model = ae.rt.MJCFCharModel('cpu'); model.load(str(ae.rt.MODEL/'humanoid_uefn.xml'))
    meta = json.loads((ae.rt.MODEL/'limits.json').read_text()); rig = json.loads((ROOT/meta['source_rig']).read_text())
    geometry = json.loads((ROOT/'Saved/MimicKitCrawl/geometry.json').read_text())
    names = model.get_body_names(); entries = []
    for i, label in ((2,'crawl'),(3,'crawl_idle')):
        clip = manifest['clips'][i]; source = Path(clip['robot_motion']); motion = pickle.loads(source.read_bytes())
        before = np.asarray(motion['frames']); frames = before.copy()
        report = dict(id=label, original=str(source), original_sha256=ae.sha(source))
        if label == 'crawl_idle':
            conversion = json.loads(source.with_name('04_crawl_idle_conversion.json').read_text())
            wanted = wanted_poses(conversion['source'],model,meta,rig)
            frames, solve = fit_idle(model,frames,wanted,geometry)
            pos, quat = ae.fk(model,frames); rotations = R.from_quat(quat.reshape(-1,4)).as_matrix().reshape(len(frames),len(names),3,3)
            contact = {}
            for name in ('right_hand','left_hand'):
                j = names.index(name); g = next(g for g in geometry['shapes'] if g['bone']==name)
                bottoms = (pos[:,j,2]+(rotations[:,j]@np.array(g['position']))[:,2]
                           -np.abs((rotations[:,j]@np.array(g['axes']))[:,2,:])@(np.array(g['dimensions'])/2))
                error = (R.from_matrix(wanted[:,j,:3,:3]).inv()*R.from_quat(quat[:,j])).magnitude()
                assert abs(bottoms).max()<2e-6 and error.max()<3e-6
                contact[name] = dict(max_abs_floor_gap_m=float(abs(bottoms).max()), max_orientation_error_rad=float(error.max()))
            report.update(hand_contact=contact, fitting=solve)
            # The imported idle already closes; only float conversion residue differs.
            pp,qq=ae.fk(model,frames)
            assert np.linalg.norm(pp[-1]-pp[0],axis=-1).max()<2e-6
            motion['loop_mode'] = 1
        else:
            frames, closure = close_crawl_cycle(model,frames)
            report['cycle_closure'] = closure
            conversion=json.loads(source.with_name('03_crawl_conversion.json').read_text())
            wanted=wanted_poses(conversion['source'],model,meta,rig)
            frames,contact=fit_crawl(model,frames,wanted,geometry)
            motion['fps']*=contact['resample_factor']
            report['hand_contact']=contact
            motion['loop_mode'] = 1
        pp,qq=ae.fk(model,frames)
        seam = float(np.linalg.norm((pp[-1]-pp[-1,:1])-(pp[0]-pp[0,:1]),axis=-1).max())
        angle = float((R.from_quat(qq[-1]).inv()*R.from_quat(qq[0])).magnitude().max())
        assert seam<2e-6 and angle<3e-6
        report.update(relative_position_seam_m=seam,rotation_seam_rad=angle)
        motion['frames'] = frames
        dest=out/(label+'.pkl');dest.write_bytes(pickle.dumps(motion))
        report.update(file=str(dest),sha256=ae.sha(dest),loop_mode=motion['loop_mode'])
        entries.append(report)
    (out/'report.json').write_text(json.dumps(dict(motions=entries,ae_dataset_changed=False,policy_lafan_clips=0),indent=2))
    print(json.dumps([{k:v for k,v in r.items() if k!='fitting'} for r in entries]))


if __name__=='__main__':main()
