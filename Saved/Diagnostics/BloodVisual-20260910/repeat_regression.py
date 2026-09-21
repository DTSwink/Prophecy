import unreal,builtins,json
s=builtins._blood_visual;m=s['fighter_manager'];w=m.get_world();a=sorted(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent),key=lambda a:a.get_name())[1];c=next(c for c in a.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='PhysicalMesh')
mid=c.get_material(0);rt=m.get_first_paint_render_target();before=m.get_debug_stats_string();assert not m.editor_auto_create_blood_materials
first=m.debug_paint_uv(c,unreal.Vector2D(.1,.1),2,.1,0);second=m.debug_paint_uv(c,unreal.Vector2D(.2,.2),2,.1,0);m.flush_pending_blood_stamps();assert first and second
same=c.get_material(0)==mid and m.get_first_paint_render_target()==rt;assert same
g=unreal.get_default_object(unreal.GameplayStatics);t=unreal.Transform(location=unreal.Vector(50000,52000,2000));x=g.call_method('BeginDeferredActorSpawnFromClass',args=(w,unreal.StaticMeshActor,t,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN));x.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'));x.static_mesh_component.set_material(0,unreal.load_asset('/Engine/BasicShapes/BasicShapeMaterial'));g.call_method('FinishSpawningActor',args=(x,t))
try:
 rejected=not m.debug_paint_uv(x.static_mesh_component,unreal.Vector2D(.5,.5),5,1,0);assert rejected
finally:x.destroy_actor()
r={'debug_uv_repeat_accepted':first and second,'same_mid_and_rt':same,'unmapped_receiver_rejected':rejected,'auto_generation':m.editor_auto_create_blood_materials,'before':before,'after':m.get_debug_stats_string()};(s['out']/'repeat-regression.json').write_text(json.dumps(r,indent=2));print(r)
