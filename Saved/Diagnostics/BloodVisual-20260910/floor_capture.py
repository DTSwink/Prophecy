import unreal,builtins,json,sys
s=builtins._blood_visual;w=s['world'];phase=sys.argv[1]
s['actors']['FloorDecals'].set_actor_tick_enabled(False)
unreal.SystemLibrary.flush_persistent_debug_lines(w)
cap=s['actors']['Capture'];c=cap.get_component_by_class(unreal.SceneCaptureComponent2D)
pp=c.post_process_settings;pp.override_auto_exposure_apply_physical_camera_exposure=True;pp.auto_exposure_apply_physical_camera_exposure=False;c.post_process_settings=pp
cam=s['actors']['camera_floor'];cap.set_actor_transform(cam.get_actor_transform(),False,True)
c.primitive_render_mode=unreal.SceneCapturePrimitiveRenderMode.PRM_RENDER_SCENE_PRIMITIVES;c.show_only_actors=[];c.fov_angle=45
light=s['actors']['light_static'];light.set_actor_transform(cam.get_actor_transform(),False,True);light.get_component_by_class(unreal.RectLightComponent).set_intensity(200)
for n in ('key','fill'):s['actors'][n].get_component_by_class(unreal.DirectionalLightComponent).set_intensity(2)
pp=c.post_process_settings;pp.override_auto_exposure_bias=True;pp.auto_exposure_bias=6;c.post_process_settings=pp
unreal.AutomationLibrary.finish_loading_before_screenshot()
c.capture_scene();unreal.RenderingLibrary.export_render_target(w,c.texture_target,str(s['out']),'floor_'+phase+'.png')
grid=s['actors']['FloorDecals'].get_component_by_class(unreal.ProphecyFoliageDecalGridComponent)
m=grid.decal_material
report={'material':m.get_path_name(),'parent':m.parent.get_path_name(),'textures':{},'scalars':{},'vectors':{}}
for n in unreal.MaterialEditingLibrary.get_texture_parameter_names(m):report['textures'][str(n)]=str(unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(m,n))
for n in unreal.MaterialEditingLibrary.get_scalar_parameter_names(m):report['scalars'][str(n)]=str(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(m,n))
for n in unreal.MaterialEditingLibrary.get_vector_parameter_names(m):report['vectors'][str(n)]=str(unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(m,n))
(s['out']/'floor-material.json').write_text(json.dumps(report,indent=2));print(report)
