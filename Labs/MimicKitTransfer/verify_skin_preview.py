"""Read back all imported frames, verify local tracks and untouched source assets."""
import json,math,hashlib
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve();out=root/'Saved/MimicKitTransfer/no-armature-3913'
mesh=unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin');reports=[]
for tag in ('Newton','Jolt'):
    data=json.loads((out/f'skin_{tag}.json').read_text());seq=unreal.load_asset(data['asset'])
    names=[t['name'] for t in data['tracks']];posmax=0.;rotmax=0.
    for frame in range(data['frames']):
        transforms=unreal.AnimationLibrary.get_bone_poses_for_frame(seq,names,frame,False,mesh)
        assert len(transforms)==len(names)
        for t,track in zip(transforms,data['tracks']):
            pos=t.translation;q=t.rotation;p=track['positions'][frame];r=track['rotations'][frame]
            posmax=max(posmax,math.sqrt(sum((a-b)**2 for a,b in zip((pos.x,pos.y,pos.z),p))))
            dot=abs(sum(a*b for a,b in zip((q.x,q.y,q.z,q.w),r)))
            norm=math.sqrt(sum(a*a for a in (q.x,q.y,q.z,q.w))*sum(a*a for a in r))
            rotmax=max(rotmax,math.degrees(2*math.acos(min(1.,dot/norm))))
    reports.append(dict(asset=data['asset'],frames=data['frames'],bones=len(names),max_position_error_cm=posmax,max_rotation_error_degrees=rotmax))
    assert posmax<.01 and rotmax<.01,reports[-1]
rig=json.loads((root/'Saved/MimicKitUEFN/source-rig.json').read_text())
hashes={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in rig['source_files']}
assert all(hashes[n]==v['sha256'] for n,v in rig['source_files'].items())
dirty=sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
assert dirty==json.loads((out/'skin-import-receipt.json').read_text())['dirty_before']
receipt=dict(passed=True,clips=reports,original_assets_unchanged=hashes,dirty_packages=dirty)
(out/'skin-verification.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
