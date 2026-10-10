import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);w=ed.get_game_world()
if w:
 a=unreal.GameplayStatics.get_player_pawn(w,0);m=a.get_pose_reference_mesh()
 def pos(v):return [v.x,v.y,v.z]
 result={'tick':a.get_editor_property('absolute tick debug'),'physical':{b:pos(m.get_socket_location(b)) for b in ['upperarm_r','lowerarm_r','hand_r','clavicle_r','pelvis']}}
 names,future,presented,alpha=a.read_nn_future_world_pose()
 result['nn']={str(n):pos(t.translation) for n,t in zip(names,presented) if str(n) in ['upperarm_r','lowerarm_r','hand_r','clavicle_r','pelvis']}
 print(json.dumps(result));(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordDraw20261010/reach-pose.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
else:print('no play')
