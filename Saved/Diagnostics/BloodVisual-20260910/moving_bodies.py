import unreal,builtins,json,sys
s=builtins._blood_visual;w=s['world'];backend=sys.argv[1] if len(sys.argv)>1 else 'jolt'
if 'motion_handle' in s: unreal.unregister_slate_post_tick_callback(s.pop('motion_handle'))
cap=s['actors']['Capture'];capture=cap.get_component_by_class(unreal.SceneCaptureComponent2D)
capture.fov_angle=35;capture.primitive_render_mode=unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST
rt=unreal.RenderingLibrary.create_render_target2d(w,1280,900,unreal.TextureRenderTargetFormat.RTF_RGBA8,unreal.LinearColor(0,0,0,1));capture.texture_target=rt;s['capture_rt']=rt
unreal.AutomationLibrary.finish_loading_before_screenshot()
report={'backend':backend,'world':w.get_path_name(),'cases':{}}
s['motion_report']=report
def capture_body(name,phase):
 a=s['actors'][name];c=s['meshes'][name];center,ext=a.get_actor_bounds(False)
 offset=unreal.Vector(-220,-260,110) if name=='static' else unreal.Vector(-210,-80,35)
 loc=center+offset;rot=unreal.MathLibrary.find_look_at_rotation(loc,center)
 cap.set_actor_location_and_rotation(loc,rot,False,True);capture.show_only_actors=[a]
 light=s['actors']['light_static'];light.set_actor_location_and_rotation(loc,rot,False,True);light.get_component_by_class(unreal.RectLightComponent).set_intensity(80)
 capture.capture_scene();unreal.RenderingLibrary.export_render_target(w,rt,str(s['out']),name+'_'+backend+'_moving_'+phase+'.png')
 mid=c.get_material(0);mask=mid.get_texture_parameter_value('BloodMaskRT')
 unreal.RenderingLibrary.export_render_target(w,mask,str(s['out']),name+'_'+backend+'_mask_'+phase+'.png')
 unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.BloodVisualBody BloodCheck_'+name+' state')
 state=json.loads((s['out']/'body-state.json').read_text(encoding='utf-8-sig'))
 state.update({'mid':mid.get_path_name(),'mask':mask.get_path_name(),'location':[center.x,center.y,center.z],'rotation':str(a.get_actor_rotation())})
 report['cases'].setdefault(name,{})[phase]=state
for name in ('static','sword'):
 unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.BloodVisualBody BloodCheck_'+name+' '+backend+' 0 0 0 0 0 0')
 body=s['actors'][name].get_component_by_class(unreal.ProphecyJoltBodyComponent)
 if body:body.automatic_step=True
 capture_body(name,'before')
 unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.BloodVisualBody BloodCheck_'+name+' '+backend+' 20 10 5 0 0 0.25')
s['motion_frames']=0
def tick(dt):
 s['motion_frames']+=1
 if s['motion_frames']<120:return
 unreal.unregister_slate_post_tick_callback(s.pop('motion_handle'))
 try:
  for name in ('static','sword'):
   capture_body(name,'after')
   body=s['actors'][name].get_component_by_class(unreal.ProphecyJoltBodyComponent)
   if backend=='jolt':body.automatic_step=False
   else:s['meshes'][name].set_simulate_physics(False)
  capture.show_only_actors=[];capture.primitive_render_mode=unreal.SceneCapturePrimitiveRenderMode.PRM_RENDER_SCENE_PRIMITIVES
  (s['out']/('moving-bodies-'+backend+'.json')).write_text(json.dumps(report,indent=2))
  print('MOVING_BLOOD_DONE',backend)
 except Exception as e:print('MOVING_BLOOD_FAILED',e)
s['motion_handle']=unreal.register_slate_post_tick_callback(tick)
print('MOVING_BLOOD_STARTED',backend)
