import unreal,json,pathlib,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'User PIE running; leave untouched.'
s={'start':time.monotonic(),'agent':None,'rows':[],'events':[],'bindings':[],'meta':{}}
variant=sys.argv[1] if len(sys.argv)>1 else 'baseline'
settings=unreal.get_default_object(unreal.PhysicsSettings)
s['settings']=(settings.get_editor_property('max_substep_delta_time'),settings.get_editor_property('substepping'))
if variant in ['120hz','discrete120']:
    settings.set_editor_property('substepping',True);settings.set_editor_property('max_substep_delta_time',1/120)
if variant=='cubeoff':
    cube=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),unreal.StaticMeshActor) if a.get_actor_label()=='Cube')
    s['cube']=(cube,cube.get_actor_location());p=cube.get_actor_location();p.x+=10000;cube.set_actor_location(p,False,True)
def restore_editor():
    if s.get('cube'):
        a,p=s.pop('cube');a.set_actor_location(p,False,True)
def v(x):return [x.x,x.y,x.z]
def tr(x):return dict(p=v(x.translation),q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w])
def finish(err=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    for d,f in s['bindings']:
        try:d.remove_callable(f)
        except:pass
    level.editor_request_end_play()
    restore_editor()
    settings.set_editor_property('max_substep_delta_time',s['settings'][0]);settings.set_editor_property('substepping',s['settings'][1])
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/SwordJump_'+variant+'.json').write_text(json.dumps(dict(rows=s['rows'],events=s['events'],meta=s['meta'],error=err)))
    print('SWORD_JUMP',len(s['rows']),err)
def tick(dt):
    try:
        if time.monotonic()-s['start']>90:raise RuntimeError('timeout')
        w=ed.get_game_world()
        if not w:return
        a=s['agent']
        if not a:
            a=unreal.GameplayStatics.get_player_pawn(w,0)
            if not a or not a.has_valid_agent_handle():return
            restore_editor()
            s['agent']=a
            if variant.startswith('discrete'):a.set_jolt_ccd_mode(unreal.ProphecyJoltCCDMode.DISCRETE)
            s['meta']={'name':a.get_name(),'start':v(a.get_actor_location()),'debug1':a.get_editor_property('bool debug 1'),'mode':str(a.get_simulation_mode()),'inertia':a.get_sword_attached_inertia_scale(),'ccd_mode':str(a.get_jolt_ccd_mode()),'cubes':[(c.get_name(),v(c.get_actor_location())) for c in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.StaticMeshActor)]}
            a.set_generate_physical_hit_events(True)
            s['mesh']=next(m for m in a.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name()=='PhysicalMesh')
            def hit(mine,other,component,impulse,result):
                s['events'].append(dict(t=unreal.GameplayStatics.get_time_seconds(w),other=other.get_name() if other else '',component=component.get_name() if component else '',impulse=v(impulse)))
            d=s['mesh'].on_component_hit;d.add_callable(hit);s['bindings'].append((d,hit))
        t=unreal.GameplayStatics.get_time_seconds(w)
        r={'t':t,'tick':a.get_editor_property('tick debug'),'root':v(a.get_actor_location()),'attack':str(a.get_nn_attack_state()),'bones':{}}
        for bone in ['pelvis','upperarm_r','lowerarm_r','hand_r','head']:
            b=a.get_physical_body_state(bone)
            if b:r['bones'][bone]=dict(transform=tr(b[0]),v=v(b[1]),av=v(b[2]),sim=b[3])
        sword=a.get_held_sword()
        if sword:
            m=sword.get_editor_property('root_component')
            r['sword']=dict(transform=tr(m.get_world_transform()),ccd=m.get_editor_property('body_instance').get_editor_property('use_ccd'),sim=m.is_simulating_physics(),collision=str(m.get_collision_enabled()))
        s['rows'].append(r)
        if t>=3.5:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
