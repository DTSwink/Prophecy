import unreal,builtins,sys,json
s=builtins._blood_visual;w=s['world'];phase=sys.argv[1] if len(sys.argv)>1 else 'jolt_clean'
cap=s['actors']['Capture'];c=cap.get_component_by_class(unreal.SceneCaptureComponent2D)
c.capture_every_frame=False;c.capture_on_movement=False;c.fov_angle=35
unreal.AutomationLibrary.finish_loading_before_screenshot()
rt=unreal.RenderingLibrary.create_render_target2d(w,1600,900,unreal.TextureRenderTargetFormat.RTF_RGBA8,unreal.LinearColor(0,0,0,1))
c.texture_target=rt;s['capture_rt']=rt
light=s['actors']['light_static'];lc=light.get_component_by_class(unreal.RectLightComponent);lc.set_intensity(500)
old_light=light.get_actor_transform();old_mode=c.primitive_render_mode
actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor)
report=json.loads((s['out'].parent/'BloodVisual'/('instances-'+phase.split('_')[0]+'.json')).read_text())
c.primitive_render_mode=unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST
for i,name in enumerate(('ISM','HISM','PCG_CPU')):
 row_y=800+i*400
 paths={p[k] for p in report['promotions'] if p['kind']==name for k in ('source_actor','promoted_actor')}
 c.show_only_actors=[a for a in actors if a.get_path_name() in paths]
 center=unreal.Vector(300,row_y,240);loc=center+unreal.Vector(-1000,-1400,600)
 rot=unreal.MathLibrary.find_look_at_rotation(loc,center)
 cap.set_actor_location_and_rotation(loc,rot,False,True)
 light.set_actor_location_and_rotation(center+(loc-center)*.35,rot,False,True)
 c.capture_scene();unreal.RenderingLibrary.export_render_target(w,rt,str(s['out']),name+'_'+phase+'.png')
c.show_only_actors=[];c.primitive_render_mode=old_mode
light.set_actor_transform(old_light,False,True)
print('INSTANCE_IMAGES',phase)
