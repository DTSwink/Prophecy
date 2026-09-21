import unreal,json
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
print('WORLD',w.get_path_name())
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
    if any(k in a.get_name().lower() for k in ('blood','decal','sword','pose','jolt','floor')):
        print('ACTOR',a.get_path_name(),a.get_class().get_path_name())
        for c in a.get_components_by_class(unreal.MeshComponent):
            print(' MESH',c.get_name(),str(c.get_editor_property('static_mesh')) if isinstance(c,unreal.StaticMeshComponent) else '',[str(c.get_material(i)) for i in range(c.get_num_materials())])
        if isinstance(a,unreal.ProphecyBloodTexturePaintManager):
            for p in a.blood_enabled_material_pairs: print('PAIR',str(p.clean_material),str(p.blood_material))
print('SPAWN',unreal.EditorLevelLibrary.spawn_actor_from_class.__doc__)
print('HIT',unreal.HitResult.__doc__)
print('BODY',unreal.ProphecyJoltBodyComponent.create_jolt_body.__doc__ if hasattr(unreal.ProphecyJoltBodyComponent,'create_jolt_body') else dir(unreal.ProphecyJoltBodyComponent))
