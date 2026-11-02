"""Lighting/material revision confined to the owned Oil test scene."""
import unreal as u, json, shutil
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
w=ed.get_editor_world();assert 'M_OilTest' in w.get_path_name()
actors=u.get_editor_subsystem(u.EditorActorSubsystem);lib=u.MaterialEditingLibrary
assets=u.AssetToolsHelpers.get_asset_tools();root='/Game/_mygame/OilBottle'
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Studio';out.mkdir(parents=True,exist_ok=True)
for rel in ['_mygame/OilBottle/Materials/M_OilBottleGlass.uasset','_mygame/OilBottle/Materials/M_OilBottleCork.uasset','_mygame/Tests/Oil/M_OilTest.umap']:
 p=Path(u.Paths.project_content_dir())/rel;dest=out/('before-'+p.name)
 if p.exists() and not dest.exists():shutil.copy2(p,dest)
import runpy
recipe=runpy.run_path(str(Path(u.Paths.project_dir()).resolve()/"Tools/Oil/BottleMaterials.py"))
g,c,liq=recipe["build_materials"](overwrite=False)
for name in ["mat","node","scalar","color","wire","custom","compile"]:globals()[name]=recipe[name]
bp=u.load_asset(root+'/BP_OilBottle')
# Small, reproducible studio environment. Large bright cards give real specular reflections.
task=u.AssetImportTask();task.filename=str(Path(u.Paths.project_dir()).resolve()/'Tools/Oil/Source/OilStudio.hdr')
task.destination_path='/Game/_mygame/Tests/Oil/Studio';task.destination_name='T_OilStudio';task.automated=True;task.replace_existing=True;task.save=False
assets.import_asset_tasks([task]);cube=u.load_asset('/Game/_mygame/Tests/Oil/Studio/T_OilStudio');assert cube
u.SystemLibrary.execute_console_command(w,'Editor.AsyncAssetCompilationFinishAll')
def actor(cls,label,pos=(0,0,0),target=None):
 a=next((a for a in actors.get_all_level_actors() if a.get_actor_label()==label),None)
 if a is None:a=actors.spawn_actor_from_class(cls,u.Vector(*pos))
 a.set_actor_label(label);a.set_actor_location(u.Vector(*pos),False,True)
 if target:a.set_actor_rotation(u.MathLibrary.find_look_at_rotation(u.Vector(*pos),u.Vector(*target)),False)
 return a
for a in actors.get_all_level_actors():
 if isinstance(a,u.DirectionalLight):
  a.light_component.set_mobility(u.ComponentMobility.MOVABLE);a.light_component.set_intensity(1500)
  a.light_component.set_editor_property('light_source_angle',5.);a.set_actor_rotation(u.Rotator(-55,-25,0),False)
 if isinstance(a,u.SkyLight):
  sc=a.light_component;sc.set_mobility(u.ComponentMobility.MOVABLE);sc.set_editor_property('source_type',u.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP);sc.set_cubemap(None);sc.set_cubemap(cube);sc.set_intensity(1000)
  sc.set_editor_property('source_cubemap_angle',270.);sc.set_editor_property('real_time_capture',False)
  sc.set_editor_property('cast_raytraced_shadow',u.CastRayTracedShadow.DISABLED)
  sc.set_editor_property('affect_global_illumination',False);sc.set_editor_property('affect_reflection',True)
  sc.set_indirect_lighting_intensity(1.)
  sc.set_editor_property('affect_translucent_lighting',True);sc.set_editor_property('lower_hemisphere_is_black',False);sc.recapture_sky()
 if isinstance(a,u.SphereReflectionCapture):
  actors.destroy_actor(a)
base=(-980,-380,0)
for label,offset,intensity,width,height in [('Key',(-65,-65,90),2400,45,100),('Rim',(55,40,75),1800,25,90),('Fill',(70,-75,55),700,65,80)]:
 p=tuple(base[i]+offset[i] for i in range(3));a=actor(u.RectLight,'Oil_Studio_'+label,p,(-980,-380,22))
 lc=a.get_component_by_class(u.RectLightComponent);lc.set_mobility(u.ComponentMobility.MOVABLE)
 for k,v in {'intensity':intensity,'attenuation_radius':650.,'source_width':width,'source_height':height,'cast_shadows':True,'affect_translucent_lighting':True}.items():lc.set_editor_property(k,v)
for label,offset,intensity,radius in [('StripLeft',(-50,-40,18),500.,4.),('StripRight',(55,-15,25),300.,3.)]:
 p=tuple(base[i]+offset[i] for i in range(3));a=actor(u.PointLight,'Oil_Studio_'+label,p)
 a.set_actor_rotation(u.Rotator(90,0,0),False);lc=a.light_component;lc.set_mobility(u.ComponentMobility.MOVABLE)
 for k,v in {'intensity':intensity,'source_radius':radius,'source_length':55.,'attenuation_radius':500.,'cast_shadows':False,'affect_translucent_lighting':True}.items():lc.set_editor_property(k,v)
pp=actor(u.PostProcessVolume,'Oil_StudioExposure');pp.set_editor_property('unbound',True)
ps=pp.get_editor_property('settings')
for k,v in {'auto_exposure_min_brightness':7.,'auto_exposure_max_brightness':7.,'auto_exposure_bias':0.,'bloom_intensity':.08,'vignette_intensity':0.,'motion_blur_amount':0.}.items():
 ps.set_editor_property('override_'+k,True);ps.set_editor_property(k,v)
ps.set_editor_property('override_dynamic_global_illumination_method',True)
ps.set_editor_property('dynamic_global_illumination_method',u.DynamicGlobalIlluminationMethod.NONE)
ps.set_editor_property('override_reflection_method',True)
ps.set_editor_property('reflection_method',u.ReflectionMethod.SCREEN_SPACE)
pp.set_editor_property('settings',ps)
# Neutral seamless background and floor in the existing isolated scene.
bg=mat('M_OilStudioBackground','/Game/_mygame/Tests/Oil/Studio');bg.set_editor_property('shading_model',u.MaterialShadingModel.MSM_UNLIT)
wire(color(bg,'Background',(100,100,100)),u.MaterialProperty.MP_EMISSIVE_COLOR);bg.set_editor_property('two_sided',True);compile(bg)
sky=actor(u.StaticMeshActor,'Oil_StudioBackdrop',(-980,-380,0));sc=sky.static_mesh_component
# Dedicated visual-only mesh: never admit the enclosing sphere as a physical shell.
backdrop_path='/Game/_mygame/Tests/Oil/Studio/SM_Background'
backdrop=u.load_asset(backdrop_path) if u.EditorAssetLibrary.does_asset_exist(backdrop_path) else u.EditorAssetLibrary.duplicate_asset('/Engine/BasicShapes/Sphere',backdrop_path)
u.get_editor_subsystem(u.StaticMeshEditorSubsystem).remove_collisions(backdrop)
backdrop.get_editor_property('body_setup').set_editor_property('collision_trace_flag',u.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
sc.set_static_mesh(backdrop);sc.set_material(0,bg);sky.set_actor_scale3d(u.Vector(150,150,150))
sc.set_collision_enabled(u.CollisionEnabled.NO_COLLISION);sky.set_actor_enable_collision(False);sc.set_cast_shadow(False)
floor=mat('M_OilStudioFloor','/Game/_mygame/Tests/Oil/Studio');wire(color(floor,'Color',(.22,.225,.23)),u.MaterialProperty.MP_BASE_COLOR);wire(scalar(floor,'Roughness',.46),u.MaterialProperty.MP_ROUGHNESS);compile(floor)
for a in actors.get_all_level_actors():
 if a.get_actor_label()=='Oil_MeshFloor':a.static_mesh_component.set_material(0,floor)
for cmd in ['r.RefractionQuality 2','r.ScreenPercentage 100','Editor.AsyncAssetCompilationFinishAll']:u.SystemLibrary.execute_console_command(w,cmd)
# Save the scene lighting before adding temporary review actors.
for a in actors.get_all_level_actors():
 if a.get_actor_label().startswith('StudioReview'):
  actors.destroy_actor(a);continue
 if isinstance(a,u.ProphecyOilBottle):
  a.get_component_by_class(u.ProphecyOilLiquid).set_editor_property('liquid_material',liq)
for m in [g,c,liq,bp,cube,bg,floor,backdrop]:assert u.EditorAssetLibrary.save_loaded_asset(m,False)
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
print('OIL_STUDIO_SETUP_DONE')

