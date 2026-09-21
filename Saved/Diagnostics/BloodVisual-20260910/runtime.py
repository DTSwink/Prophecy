import unreal,builtins,json,sys
s=builtins._blood_visual
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world();assert w,'Start PIE first'
actors={}
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
 for tag in a.tags:
  if str(tag).startswith('BloodCheck_'):actors[str(tag)[11:]]=a
assert 'Manager' in actors,list(actors)
s['actors']=actors;s['manager']=actors['Manager']
s['meshes']={n:actors[n].get_component_by_class(unreal.MeshComponent) for n in s['meshes']}
s['world']=w
print('BLOOD_PIE_READY',list(actors),'JOLT',unreal.ProphecyJoltBlueprintLibrary.is_jolt_world_ready(w))
