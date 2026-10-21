"""Owned short current-scene test; capture cuts, wound components and painted masks."""
import unreal, pathlib, json, time, traceback, sys
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'User Play left untouched'
out = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/WoundRay'
tag = sys.argv[1] if len(sys.argv)>1 else 'test'
log = pathlib.Path(unreal.Paths.project_log_dir()) / 'GameAnimationSample3.log'
wr = {'world':None, 'handle':None, 'start':time.monotonic(), 'first':None, 'last':None, 'rows':[], 'log_offset':log.stat().st_size, 'seen':set(), 'exports':[]}
if 'WoundExportObserverV2' not in globals():
    @unreal.uclass()
    class WoundExportObserverV2(unreal.ProphecyBloodStainRenderer):
        @unreal.ufunction(override=True)
        def receive_particle_data(self, data, niagara_system, simulation_position_offset):
            try:
                for p in data:
                    if len(wr['exports'])>=100:break
                    r={'t':unreal.GameplayStatics.get_time_seconds(wr['world']),'p':str(p.position),'v':str(p.velocity),'offset':str(simulation_position_offset),'size':p.size,'traces':{}}
                    for distance in [1,5,15]:
                        hit=unreal.SystemLibrary.line_trace_single(wr['world'],p.position+p.velocity*distance,p.position-p.velocity*distance,unreal.TraceTypeQuery.ECC_NIAGARA_WOUND,True,[],unreal.DrawDebugTrace.NONE,False)
                        r['traces'][distance]=hit.export_text() if hit else None
                    wr['exports'].append(r)
                wr['manager'].call_method('ReceiveParticleData',(data,niagara_system,simulation_position_offset))
            except Exception:wr['proxy_error']=traceback.format_exc()
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(wr['handle'])
    if wr['world'] and ed.get_game_world()==wr['world']: le.editor_request_end_play()
    with log.open('rb') as f:
        f.seek(wr['log_offset']); text=f.read().decode('utf-8',errors='replace')
    (out/(tag+'-log.txt')).write_text(text,encoding='utf-8')
    (out/(tag+'.json')).write_text(json.dumps({'error':error,'proxy_error':wr.get('proxy_error'),'exports':wr['exports'],'first':wr['first'],'rows':wr['rows']},indent=2),encoding='utf-8')
def tick(dt):
    try:
        w=ed.get_game_world()
        if not w:
            if wr['world'] or time.monotonic()-wr['start']>30:finish('Play ended/startup timeout')
            return
        if not wr['world']:
            wr['world']=w
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyBloodTexturePaintManager):
                a.set_editor_property('debug_print_hits',True)
                a.set_editor_property('debug_log_rejected_hits',True)
            if 'proxy' in tag:
                wr['manager']=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor) if a.get_class().get_name()=='A_DecalManager_C')
                gs=unreal.get_default_object(unreal.GameplayStatics)
                tr=unreal.Transform(location=unreal.Vector(0,0,-10000))
                wr['proxy']=gs.call_method('BeginDeferredActorSpawnFromClass',(w,WoundExportObserverV2,tr,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
                gs.call_method('FinishSpawningActor',(wr['proxy'],tr,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
                wr['proxy'].set_actor_tick_enabled(False)
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==wr['last']:return
        wr['last']=t
        row={'t':t,'swords':[],'paint':[]}
        for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
            if 'first-only' in tag:
                for c in a.get_components_by_class(unreal.NiagaraComponent):
                    if c.get_path_name() in wr['seen']:continue
                    wr['seen'].add(c.get_path_name())
                    if c.get_asset() and c.get_asset().get_name().lower()=='ns_bloodwound':
                        c.set_emitter_enable('Fountain002',False)
                        if 'proxy' in wr:c.set_variable_object('User.decal_callback',wr['proxy'])
                    else:c.deactivate_immediate()
            if a.get_class().get_name()=='A_Sword_C':
                cuts=a.get_editor_property('cuts')
                if cuts and wr['first'] is None:wr['first']=t
                row['swords'].append({'name':a.get_name(),'cuts':[c.export_text() for c in cuts], 'niagara':[{'name':c.get_name(),'asset':str(c.get_asset()),'transform':str(c.get_world_transform()),'length':c.get_variable_float('User.length')} for c in a.get_components_by_class(unreal.NiagaraComponent)]})
                if 'cache' in tag:
                    for c in a.get_components_by_class(unreal.NiagaraComponent):
                        if not c.get_asset() or c.get_asset().get_name().lower()!='ns_bloodwound':continue
                        row['ns_active']=c.is_active()
                        cache_object=unreal.NiagaraSimCacheFunctionLibrary.create_niagara_sim_cache(w)
                        cache=unreal.NiagaraSimCacheFunctionLibrary.capture_niagara_sim_cache_immediate(cache_object,unreal.NiagaraSimCacheCreateParameters(),c)
                        if cache:
                            row['particles']={}
                            for emitter in ['Fountain001','Fountain002']:
                                def vlist(vs):return [[v.x,v.y,v.z] for v in vs]
                                row['particles'][emitter]={'local':vlist(cache.read_position_attribute('Position',emitter,False)), 'world':vlist(cache.read_position_attribute('Position',emitter,True)), 'velocity':vlist(cache.read_vector_attribute('Velocity',emitter)), 'age':list(cache.read_float_attribute('Age',emitter)), 'lifetime':list(cache.read_float_attribute('Lifetime',emitter))}
                            for victim in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.SkeletalMeshActor):
                                mesh=victim.get_component_by_class(unreal.SkeletalMeshComponent)
                                row['head']=str(mesh.get_socket_transform('head',unreal.RelativeTransformSpace.RTS_WORLD))
            if isinstance(a,unreal.ProphecyBloodTexturePaintManager):row['paint'].append(a.get_debug_stats_string())
        wr['rows'].append(row)
        end=(wr['first'] is not None and t-wr['first']>=(0.12 if 'early' in tag else 0.35)) or t>2 or time.monotonic()-wr['start']>25
        if end:
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.SkeletalMeshActor):
                c=a.get_component_by_class(unreal.SkeletalMeshComponent)
                for slot in range(c.get_num_materials()):
                    m=c.get_material(slot)
                    if isinstance(m,unreal.MaterialInstanceDynamic):
                        rt=m.get_texture_parameter_value('BloodMaskRT')
                        if rt:unreal.RenderingLibrary.export_render_target(w,rt,str(out),tag+'-'+a.get_name()+'-'+str(slot)+'.png')
                if 'visual' in tag and a.get_name()=='SkeletalMeshActor_0':
                    for owner in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
                        for ns in owner.get_components_by_class(unreal.NiagaraComponent):ns.set_visibility(False)
                        if owner.get_class().get_name()=='A_Sword_C':owner.set_actor_hidden_in_game(True)
                        for grid in owner.get_components_by_class(unreal.ProphecyFoliageDecalGridComponent):
                            for decal in grid.get_active_foliage_grid_decals():decal.set_visibility(False)
                    center=c.get_socket_location('head')
                    pos=center+unreal.Vector(-35,-65,30)
                    tr=unreal.Transform(location=pos,rotation=unreal.MathLibrary.find_look_at_rotation(pos,center))
                    gs=unreal.get_default_object(unreal.GameplayStatics)
                    cam=gs.call_method('BeginDeferredActorSpawnFromClass',(w,unreal.SceneCapture2D,tr,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
                    cam=gs.call_method('FinishSpawningActor',(cam,tr,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
                    cap=cam.get_component_by_class(unreal.SceneCaptureComponent2D)
                    cap.capture_every_frame=cap.capture_on_movement=False
                    cap.capture_source=unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
                    cap.fov_angle=35
                    cap.texture_target=unreal.RenderingLibrary.create_render_target2d(w,512,512,unreal.TextureRenderTargetFormat.RTF_RGBA8)
                    mids=[c.get_material(i) for i in range(c.get_num_materials()) if isinstance(c.get_material(i),unreal.MaterialInstanceDynamic)]
                    values=[m.get_scalar_parameter_value('BloodIntensity') for m in mids]
                    print('Wound visual material intensity',values)
                    for view,offset in enumerate([unreal.Vector(-35,-65,30),unreal.Vector(35,65,30),unreal.Vector(-45,30,20),unreal.Vector(45,-30,20)]):
                        pos=center+offset
                        cap.set_world_location_and_rotation(pos,unreal.MathLibrary.find_look_at_rotation(pos,center),False,False)
                        for label,enabled in [('painted',True),('clean',False)]:
                            for m,value in zip(mids,values):m.set_scalar_parameter_value('BloodIntensity',value if enabled else 0)
                            cap.capture_scene()
                            unreal.RenderingLibrary.export_render_target(w,cap.texture_target,str(out),tag+'-'+str(view)+'-'+label+'.png')
                    for m,value in zip(mids,values):m.set_scalar_parameter_value('BloodIntensity',value)
                    cam.destroy_actor()
            finish()
    except Exception:finish(traceback.format_exc())
wr['handle']=unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play()
print('Owned wound test started: '+tag)

