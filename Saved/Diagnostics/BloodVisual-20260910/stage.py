import unreal,json,pathlib,builtins
out=pathlib.Path(unreal.Paths.project_saved_dir()).resolve()/'Diagnostics/BloodVisual-20260910'
out.mkdir(parents=True,exist_ok=True)
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert str(w.get_path_name()).startswith('/Engine/Maps/Entry.')
for old in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
 if 'BloodVisual20260910' in [str(t) for t in old.tags]:unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(old)
s={'world':w,'actors':{},'meshes':{},'report':{'world':w.get_path_name(),'cases':{}},'out':out}
builtins._blood_visual=s
def spawn(cls,name,loc,rot=unreal.Rotator()):
 a=unreal.EditorLevelLibrary.spawn_actor_from_class(cls,unreal.Vector(*loc),rot,transient=False)
 a.set_actor_label('BloodCheck_'+name);a.tags=list(a.tags)+['BloodVisual20260910','BloodCheck_'+name];s['actors'][name]=a
 return a
manager=spawn(unreal.ProphecyBloodTexturePaintManager,'Manager',(0,0,-1000))
manager.editor_auto_create_blood_materials=True
manager.editor_auto_update_blood_materials=False
manager.editor_allow_generated_material_overwrite=False
manager.editor_save_generated_blood_materials=False
manager.flush_every_tick=False
manager.require_paintable_tag=False
manager.debug_print_hits=True
manager.brush_material=unreal.load_asset('/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle')
s['manager']=manager
assets={'static':'/Engine/BasicShapes/Cube','nanite':'/Game/Fab/Megascans/3D/Rock_shopk/Medium/shopk_tier_2/StaticMeshes/rock3','sword':'/Game/_mygame/sword/geometry/Sword_GL01_Training','character':'/Game/_mygame/SKM_UEFN_Mannequin'}
for i,(name,path) in enumerate(assets.items()):
 asset=unreal.load_asset(path);assert asset,path
 a=spawn(unreal.SkeletalMeshActor if name=='character' else unreal.StaticMeshActor,name,(i*400,0,100 if name!='character' else 0))
 c=a.get_component_by_class(unreal.SkeletalMeshComponent if name=='character' else unreal.StaticMeshComponent)
 if name=='character':c.set_skeletal_mesh_asset(asset)
 else:
  c.set_static_mesh(asset)
  if name!='static':
   for slot in range(c.get_num_materials()):c.set_material(slot,asset.get_material(slot))
 c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
 s['meshes'][name]=c
 mats=[c.get_material(j).get_path_name() for j in range(c.get_num_materials())]
 s['report']['cases'][name]={'asset':path,'materials':mats}
 for slot in range(c.get_num_materials()):
  assert manager.debug_paint_uv(c,unreal.Vector2D(.5,.5),1,0,slot),(name,slot)
 manager.clear_runtime_paint_state(True)
 if name in ('static','nanite'):c.set_mobility(unreal.ComponentMobility.STATIC)
 center,extent=a.get_actor_bounds(False)
 s['report']['cases'][name]['bounds']={'center':str(center),'extent':str(extent)}
 camera=spawn(unreal.CameraActor,'camera_'+name,(center.x,center.y-max(extent.x,extent.z,30)*4.8,center.z))
 camera.camera_component.field_of_view=35
 camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera.get_actor_location(),center),False)
for name,loc,rot,intensity in [('key',(500,-600,800),unreal.Rotator(-35,70,0),4),('fill',(500,600,500),unreal.Rotator(-25,-90,0),2)]:
 light=spawn(unreal.DirectionalLight,name,loc,rot)
 light.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property('intensity',intensity)
s['report']['material_pairs']=[{'clean':p.clean_material.get_path_name(),'blood':p.blood_material.get_path_name()} for p in manager.blood_enabled_material_pairs]
spawn(unreal.ProphecyJoltFightSetup,'JoltSetup',(0,0,-2000))
spawn(unreal.SceneCapture2D,'Capture',(0,0,2000))
floor=spawn(unreal.StaticMeshActor,'floor',(0,1600,-5))
floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
floor.static_mesh_component.set_material(0,unreal.load_asset('/Engine/BasicShapes/BasicShapeMaterial'))
floor.set_actor_scale3d(unreal.Vector(6,6,.1))
floor.static_mesh_component.set_collision_profile_name('BlockAll')
floor.static_mesh_component.set_mobility(unreal.ComponentMobility.STATIC)
cam=spawn(unreal.CameraActor,'camera_floor',(0,1150,500))
cam.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(cam.get_actor_location(),unreal.Vector(0,1600,0)),False)
cam.camera_component.field_of_view=45
decals=spawn(unreal.EditorAssetLibrary.load_blueprint_class('/Game/_mygame/blood2/A_DecalManager'),'FloorDecals',(0,1600,-1000))
decals.set_editor_property('floor',floor)
spawn(unreal.ProphecyBloodStainRenderer,'ProceduralStains',(0,0,0))
w.get_world_settings().set_editor_property('default_game_mode',unreal.GameModeBase)
w.get_world_settings().set_editor_property('global_gravity_z',0)
w.get_world_settings().set_editor_property('global_gravity_set',True)
(out/'stage.json').write_text(json.dumps(s['report'],indent=2))
print('BLOOD_STAGE_READY',json.dumps(s['report']))
