import unreal,builtins,json
s=builtins._blood_visual;w=s['world']
unreal.SystemLibrary.execute_console_command(w,'prophecy.Jolt.BloodInstances.Cleanup')
print('SCENE',s['actors']['JoltSetup'].scene_collision.enable_scene_collision())
grid=s['actors']['FloorDecals'].get_component_by_class(unreal.ProphecyFoliageDecalGridComponent)
print('GRID',grid)
hit=unreal.SystemLibrary.line_trace_single(w,unreal.Vector(-100,1600,200),unreal.Vector(-100,1600,-100),unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],unreal.DrawDebugTrace.NONE,True)
assert hit
try: print('HIT_FIELDS',unreal.get_default_object(unreal.GameplayStatics).call_method('BreakHitResult',args=(hit,)))
except Exception as e:print('BREAK_ERROR',e)
assert grid
grid.clear_foliage_decal_grid()
print('GRID_ACCEPTED',grid.add_floor_hit_to_grid(hit,40))
grid.process_pending_merges()
p=s['actors']['ProceduralStains'];p.clear_blood_stains();p.radius_jitter=0
p.add_blood_hit(unreal.Vector(100,1600,0),unreal.Vector(0,0,1),30,unreal.LinearColor(.11,0,0,1));p.flush_pending_stains()
report={'world':w.get_path_name(),'grid_stats':grid.get_foliage_decal_grid_stats_string(),'grid_decals':len(grid.get_active_foliage_grid_decals()),'grid_material':str(grid.decal_material),'procedural_count':p.active_stain_count,'procedural_material':str(p.stain_material)}
(s['out']/'floor.json').write_text(json.dumps(report,indent=2));print(report)
light=s['actors']['light_static'];cam=s['actors']['camera_floor'];light.set_actor_transform(cam.get_actor_transform(),False,True);light.get_component_by_class(unreal.RectLightComponent).set_intensity(200)
