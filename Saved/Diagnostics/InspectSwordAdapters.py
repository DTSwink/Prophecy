import unreal,json
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
rows=[]
if w:
    for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
        bodies=a.get_components_by_class(unreal.ProphecyJoltBodyComponent)
        if bodies:rows.append({'actor':a.get_path_name(),'adapters':[b.get_path_name() for b in bodies]})
print('SWORD_ADAPTERS',json.dumps(rows))
