import unreal,pathlib,json
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/HandPhysical200';p.mkdir(exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);w=ed.get_game_world()
d=dict(play_active=w is not None)
if w:
 d['paused']=unreal.GameplayStatics.is_game_paused(w);d['time']=unreal.GameplayStatics.get_time_seconds(w)
 d['agents']=[]
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  if not a.is_player_controlled():continue
  r=dict(name=a.get_name(),tick=a.get_editor_property('tick debug'),mode=str(a.get_simulation_mode()),attack=str(a.get_nn_attack_state()),jolt=a.is_jolt_physical_animation_enabled(),prediction=a.is_jolt_joint_limit_prediction_enabled())
  r['profile']=unreal.get_default_object(unreal.ProphecyPhysicalProfileLibrary).call_method('PrintPhysicalBoneProfiles',(a,0.,unreal.LinearColor(1,1,1,1)))
  r['components']=[x.get_name() for x in a.get_components_by_class(unreal.SkeletalMeshComponent)]
  d['agents'].append(r)
else:
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
 (p/'graph-before.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
(p/'state.json').write_text(json.dumps(d,indent=2,default=str),encoding='utf8')
print(json.dumps(d,default=str))
