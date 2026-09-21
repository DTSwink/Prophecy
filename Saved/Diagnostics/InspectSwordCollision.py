import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world() or ed.get_editor_world()
rows=[]
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
    sword=a.get_held_sword()
    row=dict(actor=a.get_name(),mode=str(a.get_simulation_mode()),jolt=a.is_jolt_physical_animation_enabled(),sword=str(sword),sword_simulated=a.is_sword_simulated())
    if sword:
        b=sword.root_component
        row.update(blade_class=b.get_class().get_name(),collision=str(b.get_collision_enabled()),sim=b.is_simulating_physics(),parent=str(b.get_attach_parent()),socket=str(b.get_attach_socket_name()),profile=str(b.get_collision_profile_name()),object_type=str(b.get_collision_object_type()),physics_response=str(b.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PHYSICS_BODY)))
    rows.append(row)
print(json.dumps(dict(pie=bool(ed.get_game_world()),rows=rows,dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]),indent=2))
