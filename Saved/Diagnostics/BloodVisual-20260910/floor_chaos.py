import unreal,builtins,json
s=builtins._blood_visual;w=s['world'];s['actors']['JoltSetup'].scene_collision.disable_scene_collision()
grid=s['actors']['FloorDecals'].get_component_by_class(unreal.ProphecyFoliageDecalGridComponent);grid.clear_foliage_decal_grid()
h=unreal.SystemLibrary.line_trace_single(w,unreal.Vector(-100,1600,200),unreal.Vector(-100,1600,-100),unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],unreal.DrawDebugTrace.NONE,True)
assert h;fields=unreal.get_default_object(unreal.GameplayStatics).call_method('BreakHitResult',args=(h,));assert fields[9]==s['actors']['floor']
count=grid.add_floor_hit_to_grid(h,40);assert count==52
grid.process_pending_merges()
print('CHAOS_FLOOR_ACCEPTED',count)
