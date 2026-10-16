"""Verify and display corrected motor recordings in the dedicated comparison map."""
import unreal,json,math,sys
from pathlib import Path
live='--live' in sys.argv
accepted='--accepted-transfer' in sys.argv
suffix='LiveMotor' if live else 'Bounded'
report_stem='accepted' if accepted else ('live-motor' if live else 'bounded')
out=Path(unreal.Paths.project_dir())/'Saved/MimicKitTransfer/no-armature-3913'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor.get_game_world() is None,'Preserve active Play'
assert editor.get_editor_world().get_path_name()=='/Game/_mygame/Tests/MimicKitTransfer/M_JoltTransferFailure.M_JoltTransferFailure'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(),'Preserve map edits'
dirty=lambda:sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
before=dirty()
mesh=unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
if accepted:
 record=json.loads((out/'accepted-skin-recording.json').read_text(encoding='utf-8'))
 assert len(record['clips'])==2 and all(c['frames']==301 for c in record['clips'])
 clips=[('Jolt4013','JOLT |','JOLT | checkpoint 4013 | actual recorded physics'),
        ('Newton4013','TRAINING SIMULATOR |','TRAINING SIMULATOR | checkpoint 4013 | actual recorded physics')]
else:
 record=json.loads((out/(report_stem+'-map-recording.json')).read_text(encoding='utf-8'))
 clips=[('Jolt'+suffix,'JOLT |',f'JOLT | bounded motors | failure {record["first_failure_tick"]/30:.2f}s'),
        ('Newton'+suffix,'TRAINING SIMULATOR |','TRAINING SIMULATOR | corrected bounded motors')]
updates=[]
for tag,prefix,text in clips:
 data=json.loads((out/f'skin_{tag}.json').read_text(encoding='utf-8'))
 seq=unreal.load_asset(data['asset']);assert seq
 maxpos=maxangle=0.
 for frame in range(data['frames']):
  transforms=unreal.AnimationLibrary.get_bone_poses_for_frame(seq,[t['name'] for t in data['tracks']],frame,False,mesh)
  for tr,track in zip(transforms,data['tracks']):
   p=tr.translation;q=tr.rotation;r=track['rotations'][frame]
   maxpos=max(maxpos,math.dist((p.x,p.y,p.z),track['positions'][frame]))
   v=(q.x,q.y,q.z,q.w);dot=abs(sum(a*b for a,b in zip(v,r)))
   maxangle=max(maxangle,math.degrees(2*math.acos(min(1.,dot/math.sqrt(sum(a*a for a in v)*sum(a*a for a in r))))))
 assert maxpos<.01 and maxangle<.01,(tag,maxpos,maxangle)
 rig=[a for a in actors if isinstance(a,unreal.SkeletalMeshActor) and a.get_actor_label().startswith(prefix)]
 label=[a for a in actors if isinstance(a,unreal.TextRenderActor) and a.get_actor_label().startswith(prefix)]
 assert len(rig)==len(label)==1
 updates.append((rig[0],label[0],seq,text,dict(tag=tag,asset=seq.get_path_name(),frames=data['frames'],max_position_error_cm=maxpos,max_rotation_error_deg=maxangle)))
for rig,label,seq,text,report in updates:
 c=rig.skeletal_mesh_component
 c.override_animation_data(seq,True,True,0.,.25);c.set_update_animation_in_editor(True)
 rig.set_actor_label(text);label.text_render.set_text(text);label.set_actor_label(text+' - label')
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert levels.save_current_level()
assert before==dirty(),'Unexpected content edits'
cameras=[a for a in actors if a.get_actor_label()=='Comparison camera']
assert len(cameras)==1
levels.pilot_level_actor(cameras[0])
receipt=dict(clips=[u[-1] for u in updates],dirty_preserved=before,recorded_physics=True,live_unreal_policy=False,playback_rate=.25)
(out/(report_stem+'-preview-refreshed.json')).write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2))
levels.editor_play_simulate()
