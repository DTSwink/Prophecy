import unreal, json, pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world() or ed.get_editor_world()
rows=[]
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
    r=dict(name=a.get_name(),label=a.get_actor_label(),mode=str(a.get_simulation_mode()),interpolation=str(a.get_nn_interpolation_mode()),position=str(a.get_actor_location()))
    for p in ['tick debug','tick_debug','bool codex','locomotion_input','simulation_mode']:
        try:r[p]=str(a.get_editor_property(p))
        except:pass
    rows.append(r)
print(json.dumps(dict(pie=bool(ed.get_game_world()),actors=rows,dirty=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]),indent=2))
