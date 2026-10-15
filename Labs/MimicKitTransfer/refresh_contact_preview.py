"""Switch only the dedicated recorded comparison to the new contact rollout."""
import unreal,json,math
from pathlib import Path
out=Path(unreal.Paths.project_dir())/'Saved/MimicKitTransfer/no-armature-3913'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor.get_game_world() is None,'User Play active; leave it untouched'
assert editor.get_editor_world().get_path_name()=='/Game/_mygame/Tests/MimicKitTransfer/M_JoltTransferFailure.M_JoltTransferFailure'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(),'Preserve existing map edits'
dirty=lambda:sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
before=dirty()
data=json.loads((out/'skin_JoltContact.json').read_text())
seq=unreal.load_asset(data['asset']);assert seq
mesh=unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin')
maxpos=maxangle=0.
for frame in range(data['frames']):
    transforms=unreal.AnimationLibrary.get_bone_poses_for_frame(seq,[t['name'] for t in data['tracks']],frame,False,mesh)
    for tr,track in zip(transforms,data['tracks']):
        p=tr.translation;q=tr.rotation;r=track['rotations'][frame]
        maxpos=max(maxpos,math.dist((p.x,p.y,p.z),track['positions'][frame]))
        v=(q.x,q.y,q.z,q.w);dot=abs(sum(a*b for a,b in zip(v,r)))
        maxangle=max(maxangle,math.degrees(2*math.acos(min(1.,dot/math.sqrt(sum(a*a for a in v)*sum(a*a for a in r))))))
assert maxpos<.01 and maxangle<.01,(maxpos,maxangle)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
rig=[a for a in actors if isinstance(a,unreal.SkeletalMeshActor) and a.get_actor_label().startswith('JOLT |')]
label=[a for a in actors if isinstance(a,unreal.TextRenderActor) and a.get_actor_label().startswith('JOLT |')]
assert len(rig)==len(label)==1
report=json.loads((out/'contact-map-recording.json').read_text())
text=f'JOLT | predictive contacts OFF | failure {report["first_failure_tick"]/30:.2f}s'
c=rig[0].skeletal_mesh_component
c.override_animation_data(seq,True,True,0.,.25);c.set_update_animation_in_editor(True)
rig[0].set_actor_label(text);label[0].text_render.set_text(text);label[0].set_actor_label(text+' - label')
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
assert before==dirty(),'Unexpected content change'
receipt=dict(asset=seq.get_path_name(),max_position_error_cm=maxpos,max_rotation_error_deg=maxangle,
    dirty_preserved=before,recorded_physics=True,live_unreal_policy=False,first_failure_tick=report['first_failure_tick'])
(out/'contact-preview-refreshed.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
