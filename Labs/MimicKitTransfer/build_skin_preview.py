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

if __name__=='__main__':main()
