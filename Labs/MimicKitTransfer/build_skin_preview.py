"""Map recorded reduced-body physics to the original weighted skeleton; no UE writes."""
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation as R

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitTransfer/no-armature-3913'
ASSETS=OUT/'source/assets/uefn'
meta=json.loads((ASSETS/'limits.json').read_text())
rig=json.loads((ROOT/'Saved/MimicKitUEFN/source-rig.json').read_text())
bones=rig['skeleton']; indices={b['name']:i for i,b in enumerate(bones)}
names=[n.attrib['name'] for n in ET.parse(ASSETS/'humanoid_uefn.xml').getroot().find('worldbody').iter('body')]
basis=R.from_euler('z',90,degrees=True)

def matrix(p,q):
    m=np.eye(4);m[:3,:3]=R.from_quat(q).as_matrix();m[:3,3]=p;return m

def frame(f):return matrix(f['position'],f['quaternion'])
def ue_frame(f):return matrix(np.array(f['position_cm'])/100,f['rotation_xyzw'])

to_ue=matrix([0,0,0],basis.inv().as_quat())
locals_ref=[ue_frame(b['local']) for b in bones]
to_mj=np.linalg.inv(to_ue)
# Body origins need not be bone origins: exported foot bodies differ by 0.531 mm.
# Bind using the actual skeleton, preserving that physical body-to-bone offset.
bone_refs={b['name']:to_mj@ue_frame(b['component']) for b in bones}
offsets={n:np.linalg.inv(frame(meta['body_frames'][n]))@bone_refs[meta['groups'][n]['anchor']] for n in names}
anchor_to_body={indices[meta['groups'][n]['anchor']]:k for k,n in enumerate(names)}

def map_pose(state):
    desired={i:to_ue@matrix(state[k,:3],state[k,3:7])@offsets[names[k]] for i,k in anchor_to_body.items()}
    world=[];local=[]
    for i,b in enumerate(bones):
        parent=world[b['parent']] if b['parent']>=0 else np.eye(4)
        component=desired[i] if i in desired else parent@locals_ref[i]
        local.append(np.linalg.inv(parent)@component);world.append(component)
    return np.array(local),np.array(world)

def accepted_transfer(world):
    """Prepare the verified controller's real trajectories, without opening UE."""
    receipt=json.loads((OUT/'verified_transfer.json').read_text())
    assert receipt['accepted'] and receipt['native_successes']==16
    for name,digest in receipt['sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    assert 0<=world<16
    folder=OUT/'causal_transfer';stem='local_finetune4013_phases16'
    mj_path=folder/(stem+'.npz');jolt_path=folder/(stem+'_self0_native_v40p8_point.npz')
    with np.load(mj_path) as mj,np.load(jolt_path) as jolt:
        clips=[('Newton4013',np.concatenate([mj['initial'][world][None],mj['states'][:,world]]),mj_path),
               ('Jolt4013',jolt['world'+str(world)].copy(),jolt_path)]
    np.testing.assert_allclose(clips[0][1][0],clips[1][1][0],atol=1e-4,rtol=0)
    reports=[]
    for tag,states,path in clips:
        destination=OUT/f'skin_{tag}.json'
        assert not destination.exists(),'Preserve existing preview payload'
        assert len(states)==301 and np.isfinite(states).all()
        poses=[];collider_error=0.
        for state in states:
            local,component=map_pose(state);poses.append(local)
            for k,name in enumerate(names):
                for bone in meta['groups'][name]['colliders_from']:
                    offset=np.linalg.inv(frame(meta['body_frames'][name]))@bone_refs[bone]
                    expected=to_ue@matrix(state[k,:3],state[k,3:7])@offset
                    collider_error=max(collider_error,float(np.max(np.abs(expected-component[indices[bone]]))))
        assert collider_error<1e-7,collider_error
        poses=np.asarray(poses);tracks=[]
        for i,bone in enumerate(bones):
            quats=R.from_matrix(poses[:,i,:3,:3]).as_quat()
            for t in range(1,len(quats)):
                if quats[t]@quats[t-1]<0:quats[t]*=-1
            tracks.append(dict(name=bone['name'],positions=(poses[:,i,:3,3]*100).tolist(),rotations=quats.tolist()))
        # The side-by-side map keeps runners in view. Only display-root XY changes;
        # every physical bone's height and rotation remains the recorded result.
        by_name={t['name']:t for t in tracks}
        by_name['root']['positions']=[[-p[0],-p[1],0] for p in by_name['pelvis']['positions']]
        payload=dict(schema=1,title=f'{tag} | checkpoint4013 | actual recorded physics; XY centered only',
            fps=30,frames=len(states),asset=f'/Game/_mygame/Tests/MimicKitTransfer/AS_{tag}',
            source=str(path.relative_to(OUT)),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            phase=world/16,tracks=tracks)
        destination.write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8')
        reports.append(dict(tag=tag,frames=len(states),phase=world/16,
            collider_transform_max_error=collider_error,payload_sha256=hashlib.sha256(destination.read_bytes()).hexdigest()))
    result=dict(clips=reports,checkpoint=receipt['checkpoint'],body_count=15,original_bone_count=len(bones),
        purpose='Prepared recorded-physics comparison, not a live Unreal policy',unreal_modified=False)
    (OUT/'accepted-skin-recording.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


def main():
    reference=np.array([np.r_[meta['body_frames'][n]['position'],meta['body_frames'][n]['quaternion']] for n in names])
    _,bind=map_pose(reference)
    expected=np.array([ue_frame(b['component']) for b in bones])
    bind_error=float(np.abs(bind-expected).max());assert bind_error<1e-7,bind_error
    mapping={n:dict(anchor=meta['groups'][n]['anchor'],body_to_bone_matrix_m=offsets[n].tolist(),colliders_from=meta['groups'][n]['colliders_from']) for n in names}
    reports=[]
    for tag,title,source in [('Newton','Training simulator - recorded physics','newton_phase_0.000.npz'),('Jolt','Jolt - failed transfer diagnostic','jolt_phase_0.000.npz')]:
        path=OUT/source;states=np.load(path)['states'];tracks=[];localposes=[];components=[]
        for s in states:
            l,c=map_pose(s);localposes.append(l);components.append(c)
        localposes=np.array(localposes);components=np.array(components)
        assert np.isfinite(localposes).all()
        # Every original collider bone follows its assigned rigid body exactly.
        collider_error=0.
        for k,n in enumerate(names):
            for bone in meta['groups'][n]['colliders_from']:
                off=np.linalg.inv(frame(meta['body_frames'][n]))@bone_refs[bone]
                desired=np.array([to_ue@matrix(s[k,:3],s[k,3:7])@off for s in states])
                collider_error=max(collider_error,float(np.abs(desired-components[:,indices[bone]]).max()))
        assert collider_error<1e-7,collider_error
        for i,b in enumerate(bones):
            quats=R.from_matrix(localposes[:,i,:3,:3]).as_quat()
            for t in range(1,len(quats)):
                if quats[t]@quats[t-1]<0:quats[t]*=-1
            tracks.append(dict(name=b['name'],positions=(localposes[:,i,:3,3]*100).tolist(),rotations=quats.tolist()))
        payload=dict(schema=1,title=title,fps=30,frames=len(states),asset=f'/Game/_mygame/Tests/MimicKitTransfer/AS_Rig15_{tag}_3913',
                     source=source,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),tracks=tracks)
        (OUT/f'skin_{tag}.json').write_text(json.dumps(payload,separators=(',',':')))
        reports.append(dict(tag=tag,frames=len(states),duration_s=(len(states)-1)/30,collider_transform_max_error=collider_error))
    result=dict(schema=1,mesh=rig['mesh'],body_count=15,original_bone_count=len(bones),weight_changes=False,
                omitted_bones='original reference local transforms',bind_matrix_max_error=bind_error,bodies=mapping,clips=reports)
    (OUT/'skin-mapping.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(bind_error=bind_error,clips=reports),indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--accepted-transfer',action='store_true')
    parser.add_argument('--phase-index',type=int,default=6,help='One of the sixteen verified initial phases')
    args=parser.parse_args()
    if args.accepted_transfer:accepted_transfer(args.phase_index)
    else:main()
