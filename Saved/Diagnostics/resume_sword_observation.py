import unreal,builtins,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);w=ed.get_game_world();a=unreal.GameplayStatics.get_player_pawn(w,0)
for name,c in [('sword',a.get_held_sword().get_editor_property('root_component'))]+[(x.get_name(),x.get_editor_property('static_mesh_component')) for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.StaticMeshActor) if x.get_name()=='StaticMeshActor_2']:
 print(name,'transform',c.get_world_transform(),'collision',c.get_collision_enabled(),'channel',c.get_collision_object_type(),'bounds',c.get_local_bounds())
 try:
  b=c.get_editor_property('static_mesh').get_editor_property('body_setup');print(name,'body',b)
  g=b.get_editor_property('agg_geom');print('boxes',g.get_editor_property('box_elems'));print('convex',g.get_editor_property('convex_elems'))
 except Exception as e:print(e)
s=builtins._sword_jump_observation;s['paused']=False;s['passed_pause']=True
unreal.GameplayStatics.set_game_paused(w,False)
