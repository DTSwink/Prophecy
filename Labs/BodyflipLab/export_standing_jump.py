"""Run through Tools/RunUnrealRemote.py. Read-only asset sampling; no PIE/save."""
import unreal, json, pathlib, hashlib
out=pathlib.Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Labs/BodyflipLab/data')
names=json.loads((out/'manifest.json').read_text(encoding='utf-8'))['names']
folder='/Game/Characters/UEFN_Mannequin/Animations/Jump/'
selected=['M_Relaxed_Jump_F_Start_Stand_Lfoot','M_Relaxed_Jump_F_Start_Stand_Rfoot']
options=unreal.AnimPoseEvaluationOptions(evaluation_type=unreal.AnimDataEvalType.RAW,should_retarget=False,extract_root_motion=False)
clips=[]
for name in selected:
    asset=unreal.load_asset(folder+name)
    if not asset: raise RuntimeError('Missing '+name)
    duration=asset.get_play_length(); frames=[]
    for i in range(round(duration*60)+1):
        pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(asset,min(i/60,duration),options)
        row=[]
        for bone in names:
            tr=unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.WORLD)
            p,q=tr.translation,tr.rotation
            row.append([p.x,p.y,p.z,q.x,q.y,q.z,q.w])
        frames.append(row)
    source=out.parents[2]/'Content'/('Characters/UEFN_Mannequin/Animations/Jump/'+name+'.uasset')
    clips.append(dict(name=name,asset=folder+name,fps=60,duration=duration,frames=frames,sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
(out/'jumps-standing.json').write_text(json.dumps(dict(schema='ue-component-cm-quat-xyzw',names=names,clips=clips),separators=(',',':')),encoding='utf-8')
print('BODYFLIP_JUMPS',[(c['name'],len(c['frames']),c['frames'][0][0][:3],c['frames'][-1][0][:3]) for c in clips])
