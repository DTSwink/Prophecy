import unreal,pathlib,json,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
out={'playing':bool(w),'agents':[]}
if w:
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  sword=a.get_held_sword();state=a.get_physical_body_state('sword')
  r={'agent':a.get_name(),'held':bool(sword),'available':state is not None}
  if state:
   pose,v,omega,sim=state
   r.update(position=[pose.translation.x,pose.translation.y,pose.translation.z],linear=[v.x,v.y,v.z],angular=[omega.x,omega.y,omega.z],simulating=sim)
   assert all(math.isfinite(x) for k in ['position','linear','angular'] for x in r[k])
  if sword:assert state is not None,r
  else:assert state is None,r
  out['agents'].append(r)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordBodyState20261006'
(p/'live-read.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
