import builtins,unreal,sys,json
s=builtins._blood_visual;w=s['world']
unreal.AutomationLibrary.finish_loading_before_screenshot()
phase=sys.argv[1] if len(sys.argv)>1 else 'painted'
names=sys.argv[2:] or list(s['meshes'])
cap=s['actors']['Capture'];c=cap.get_component_by_class(unreal.SceneCaptureComponent2D)
c.capture_every_frame=False;c.capture_on_movement=False
c.capture_source=unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
c.fov_angle=35
pp=c.post_process_settings
pp.override_auto_exposure_method=True;pp.auto_exposure_method=unreal.AutoExposureMethod.AEM_MANUAL
pp.override_bloom_intensity=True;pp.bloom_intensity=0
pp.override_auto_exposure_bias=True;pp.auto_exposure_bias=0
c.post_process_settings=pp
rt=unreal.RenderingLibrary.create_render_target2d(w,1280,900,unreal.TextureRenderTargetFormat.RTF_RGBA8,unreal.LinearColor(0,0,0,1))
c.texture_target=rt;s['capture_rt']=rt
for name in names:
 cam=s['actors']['camera_'+name]
 cap.set_actor_location_and_rotation(cam.get_actor_location(),cam.get_actor_rotation(),False,True)
 c.capture_scene()
 unreal.RenderingLibrary.export_render_target(w,rt,str(s['out']),name+'_'+phase+'.png')
print('BLOOD_RENDERED',names,phase)
