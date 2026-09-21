import unreal,builtins,json,sys
s=builtins._blood_visual;w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world();assert w
if 'fighter_manager' in s:
 try:valid=unreal.SystemLibrary.is_valid(s['fighter_manager']) and s['fighter_manager'].get_world()==w
 except:valid=False
 if not valid:s.pop('fighter_manager',None);s.pop('fighter_capture',None);s.pop('fighter_light',None)
backend=sys.argv[1] if len(sys.argv)>1 else 'jolt'
g=unreal.get_default_object(unreal.GameplayStatics)
def spawn(cls):
 t=unreal.Transform();a=g.call_method('BeginDeferredActorSpawnFromClass',args=(w,cls,t,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN))
 a.tags=list(a.tags)+['BloodVisual20260910'];return g.call_method('FinishSpawningActor',args=(a,t))
agents=sorted(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent),key=lambda a:a.get_name());a=agents[1]
if backend=='chaos':
 a.disable_jolt_physical_animation();assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
else:assert a.is_jolt_physical_animation_enabled()
c=next(c for c in a.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='PhysicalMesh')
if 'fighter_manager' not in s:
 managers=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyBloodTexturePaintManager);assert len(managers)==1
 manager=managers[0];s['fighter_manager']=manager
 assert not manager.editor_auto_create_blood_materials
 manager.flush_every_tick=False;manager.debug_print_hits=True
 s['fighter_capture']=spawn(unreal.SceneCapture2D)
manager=s['fighter_manager'];manager.clear_runtime_paint_state(True)
if 'fighter_light' not in s:
 s['fighter_light']=spawn(unreal.RectLight)
 light_component=s['fighter_light'].get_component_by_class(unreal.RectLightComponent);light_component.set_cast_shadows(False);light_component.set_editor_property('source_width',100);light_component.set_editor_property('source_height',100)
light=s['fighter_light'];light_component=light.get_component_by_class(unreal.RectLightComponent)
light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
light_component.set_attenuation_radius(1000)
cap=s['fighter_capture'];sc=cap.get_component_by_class(unreal.SceneCaptureComponent2D);sc.capture_every_frame=False;sc.capture_on_movement=False;sc.capture_source=unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR;sc.fov_angle=35
pp=sc.post_process_settings;pp.override_auto_exposure_method=True;pp.auto_exposure_method=unreal.AutoExposureMethod.AEM_MANUAL;pp.override_auto_exposure_bias=True;pp.auto_exposure_bias=0;pp.override_auto_exposure_apply_physical_camera_exposure=True;pp.auto_exposure_apply_physical_camera_exposure=False;pp.override_bloom_intensity=True;pp.bloom_intensity=0;sc.post_process_settings=pp
rt=unreal.RenderingLibrary.create_render_target2d(w,1280,1000,unreal.TextureRenderTargetFormat.RTF_RGBA8,unreal.LinearColor(0,0,0,1));sc.texture_target=rt;s['capture_rt']=rt
report={'backend':backend,'actor':a.get_path_name(),'component':c.get_path_name(),'jolt':a.is_jolt_physical_animation_enabled(),'chaos_simulating':c.is_simulating_physics(),'collision':str(c.get_collision_enabled()),'auto_generation':False,'hits':[]}
region_views=[]
def snapshot(phase):
 center=c.get_socket_location('pelvis')+unreal.Vector(0,0,10);loc=center+a.get_actor_forward_vector()*340+unreal.Vector(0,0,25)
 cap.set_actor_location_and_rotation(loc,unreal.MathLibrary.find_look_at_rotation(loc,center),False,True)
 light.set_actor_transform(cap.get_actor_transform(),False,True);light_component.set_intensity(50000)
 sc.capture_scene();unreal.RenderingLibrary.export_render_target(w,rt,str(s['out']),'fighter_'+backend+'_'+phase+'.png')
 mid=c.get_material(0);mask=mid.get_texture_parameter_value('BloodMaskRT') if isinstance(mid,unreal.MaterialInstanceDynamic) else None
 report[phase]={'bones':{b:str(c.get_socket_transform(b)) for b in ('head','spine_03','upperarm_l','calf_r','pelvis')},'mid':mid.get_path_name(),'mask':mask.get_path_name() if mask else None,'location':str(a.get_actor_location())}
 if mask:unreal.RenderingLibrary.export_render_target(w,mask,str(s['out']),'fighter_'+backend+'_mask_'+phase+'.png')
 for name,bone,local_point,local_normal in region_views:
  trans=c.get_socket_transform(bone);point=unreal.MathLibrary.transform_location(trans,local_point);normal=unreal.MathLibrary.transform_direction(trans,local_normal)
  loc=point+normal*95+unreal.Vector(0,0,20);cap.set_actor_location_and_rotation(loc,unreal.MathLibrary.find_look_at_rotation(loc,point),False,True)
  light.set_actor_transform(cap.get_actor_transform(),False,True);light_component.set_intensity(5000)
  sc.capture_scene();unreal.RenderingLibrary.export_render_target(w,rt,str(s['out']),'fighter_'+backend+'_'+name+'_'+phase+'.png')
unreal.AutomationLibrary.finish_loading_before_screenshot();snapshot('clean')
for bone,child in [('head',None),('spine_03',None),('upperarm_l','lowerarm_l'),('calf_r','foot_r')]:
 point=c.get_socket_location(bone)
 if child:point=(point+c.get_socket_location(child))*.5
 direction=a.get_actor_forward_vector()
 if bone=='upperarm_l':direction=a.get_actor_right_vector()*-1
 found=None;attempts=0
 allowed={'spine_03':('spine_03','spine_04','spine_05')}.get(bone,(bone,))
 for offset in (unreal.Vector(),unreal.Vector(0,0,8),unreal.Vector(0,0,-8)):
  for ray in (direction,-direction,unreal.Vector(0,0,1),unreal.Vector(0,0,-1),a.get_actor_right_vector(),-a.get_actor_right_vector()):
   attempts+=1
   hit=unreal.SystemLibrary.line_trace_single(w,point+offset+ray*90,point+offset-ray*50,unreal.TraceTypeQuery.ECC_NIAGARA_WOUND,True,[x for x in agents if x!=a],unreal.DrawDebugTrace.NONE,True)
   if not hit:continue
   fields=g.call_method('BreakHitResult',args=(hit,))
   if fields[10]!=c or str(fields[11]) not in allowed:continue
   accepted=manager.try_paint_from_hit(hit,8,1,-1)
   found={'requested':bone,'actor':fields[9].get_path_name(),'component':fields[10].get_path_name(),'bone':str(fields[11]),'impact_point':str(fields[5]),'accepted':accepted,'attempts':attempts}
   if accepted:
    trans=c.get_socket_transform(str(fields[11]));region_views.append((bone,str(fields[11]),unreal.MathLibrary.inverse_transform_location(trans,fields[5]),unreal.MathLibrary.inverse_transform_direction(trans,fields[7])))
    break
  if found and found['accepted']:break
 report['hits'].append(found or {'requested':bone,'hit':False,'attempts':attempts})
manager.flush_pending_blood_stamps();unreal.AutomationLibrary.finish_loading_before_screenshot();snapshot('painted')
s['fighter_frames']=0
def tick(dt):
 s['fighter_frames']+=1
 if s['fighter_frames']<180:return
 unreal.unregister_slate_post_tick_callback(s.pop('fighter_handle'))
 try:
  snapshot('after_movement');report['stats']=manager.get_debug_stats_string();(s['out']/('fighter-'+backend+'.json')).write_text(json.dumps(report,indent=2));print('FIGHTER_BLOOD_DONE',backend)
 except Exception as e:print('FIGHTER_BLOOD_FAILURE',e)
s['fighter_handle']=unreal.register_slate_post_tick_callback(tick)
print('FIGHTER_BLOOD_STARTED',report)
