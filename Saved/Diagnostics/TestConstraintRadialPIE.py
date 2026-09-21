"""Real ordinary Blueprint component: two Limited axes share one 20 cm radius."""
import unreal,pathlib,json,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/StandardConstraints'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Debug.MakeConstraintBlueprintFixture')
cls=unreal.load_class(None,'/Engine/Transient.CodexConstraintFixture_C');assert cls
gs=unreal.get_default_object(unreal.GameplayStatics)
s={'phase':'start','start':time.monotonic(),'rows':[]}
def finish(result,error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if ed.get_game_world():level.editor_request_end_play()
    (folder/'RadialPIE.json').write_text(json.dumps(dict(result=result,error=error,rows=s['rows']),indent=2))
    print('CONSTRAINT_RADIAL_PIE',result,error)
def tick(_):
    try:
        assert time.monotonic()-s['start']<90,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if s['phase']=='start':
            if t<.8:return
            tr=unreal.Transform(location=unreal.Vector(20000,20000,1500))
            a=gs.call_method('BeginDeferredActorSpawnFromClass',args=(w,cls,tr,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
            a=gs.call_method('FinishSpawningActor',args=(a,tr,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
            c=a.get_component_by_class(unreal.PhysicsConstraintComponent)
            m=next(m for m in a.get_components_by_class(unreal.StaticMeshComponent) if m.get_name()=='Dynamic')
            s.update(actor=a,joint=c,mesh=m,time=t,phase='admit')
        elif s['phase']=='admit' and t-s['time']>.2:
            c=s['joint'];s['origin']=s['mesh'].get_world_location()
            # Isolate radial translation from the fixed-grip fixture's 75 cm lever arm.
            c.set_world_location(s['origin'],False,True)
            anchor=next(m for m in s['actor'].get_components_by_class(unreal.StaticMeshComponent) if m.get_name()=='Anchor')
            c.set_constrained_components(s['mesh'],'None',anchor,'None')
            c.set_linear_x_limit(unreal.LinearConstraintMotion.LCM_LIMITED,20)
            c.set_linear_y_limit(unreal.LinearConstraintMotion.LCM_LIMITED,20)
            c.set_linear_position_drive(True,True,False)
            c.set_linear_velocity_drive(True,True,False)
            c.set_linear_drive_params(100,20,0)
            c.set_linear_position_target(unreal.Vector(30,30,0))
            s.update(phase='drive',time=t)
        elif s['phase']=='drive' and t-s['time']>2.0:
            delta=s['mesh'].get_world_location()-s['origin']
            radius=math.hypot(delta.x,delta.y)
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ConstraintAudit '+s['actor'].get_name())
            row=next(r for r in json.loads((folder/'World.json').read_text(encoding='utf-8-sig'))['constraints'] if r['component']==s['joint'].get_path_name())
            s['rows'].append(dict(radius_cm=radius,delta_cm=[delta.x,delta.y,delta.z],native=row))
            assert row['jolt'] and not row['chaos'],row
            assert 19.8<radius<20.4,(radius,delta)
            assert abs(delta.x-delta.y)<.2 and abs(delta.z)<.2,delta
            finish('passed')
    except Exception:finish('failed',traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
