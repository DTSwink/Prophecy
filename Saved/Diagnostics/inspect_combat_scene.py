import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_editor_world()
def vec(v):return [v.x,v.y,v.z]
def prop(o,n):
    try:return str(o.get_editor_property(n))
    except:return None
data={'pie':bool(ed.get_game_world()),'agents':[],'meshes':[]}
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
    data['agents'].append(dict(name=a.get_name(),label=a.get_actor_label(),pos=vec(a.get_actor_location()),props={n:prop(a,n) for n in ['bool debug 1','tick debug','auto_possess_player','CombatDemoEnabled','CombatDemoUseDodge','CombatDemoReverseRoles']},functions=[x for x in dir(a) if 'attack' in x or 'combat' in x]))
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.StaticMeshActor):
    data['meshes'].append(dict(name=a.get_name(),label=a.get_actor_label(),pos=vec(a.get_actor_location()),scale=vec(a.get_actor_scale3d())))
print(json.dumps(data,indent=2))
print(unreal.ProphecyAgent.get_physical_body_state.__doc__)
print(unreal.ProphecyAgent.get_nn_attack_state.__doc__)
pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/combat_scene.json').write_text(json.dumps(data,indent=2))
