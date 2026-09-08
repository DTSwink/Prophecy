"""All integer and half frames: fixed forearms, otherwise unchanged animation."""
import json
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
data=json.loads((root/'Saved/SlashChain/sword_preview.json').read_text())
original=unreal.load_asset('/Game/_mygame/Tests/SlashChain30/AS_SlashChain30_Reference')
preview=unreal.load_asset('/Game/_mygame/Tests/SlashChain30/AS_SlashChain30_ForearmClamped')
options=unreal.AnimPoseEvaluationOptions()
options.set_editor_property('should_retarget',False)
names=[t['name'] for t in data['tracks']]
length_error=other_bones_error=0.
for frame in range(910):
    time=frame/60
    pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(preview,time,options)
    source=unreal.AnimPoseExtensions.get_anim_pose_at_time(original,time,options)
    for name in names:
        p=unreal.AnimPoseExtensions.get_bone_pose(pose,name,unreal.AnimPoseSpaces.WORLD).translation
        if name in data['clamp']:
            elbow=unreal.AnimPoseExtensions.get_bone_pose(pose,name.replace('hand','lowerarm'),unreal.AnimPoseSpaces.WORLD).translation
            length_error=max(length_error,abs((p-elbow).length()-data['clamp'][name]['rest_cm'])*10)
        else:
            before=unreal.AnimPoseExtensions.get_bone_pose(source,name,unreal.AnimPoseSpaces.WORLD).translation
            other_bones_error=max(other_bones_error,(p-before).length()*10)
report={'samples':910,'forearm_max_length_error_mm':length_error,'other_bones_max_position_change_mm':other_bones_error,
        'forearm_length_cm':{k:v['rest_cm'] for k,v in data['clamp'].items()},'passed':length_error<.1 and other_bones_error<.1}
(root/'Saved/SlashChain/forearm_clamp_audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
assert report['passed']
