import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/StandardConstraints'
folder.mkdir(parents=True,exist_ok=True)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Debug.MakeConstraintBlueprintFixture')
cls=unreal.load_class(None,'/Engine/Transient.CodexConstraintFixture_C')
assert cls,'Temporary Blueprint was not compiled'
s={'start':time.monotonic(),'phase':'start','rows':[]}
gs=unreal.get_default_object(unreal.GameplayStatics)

def spawn(w,c,t):
    a=gs.call_method('BeginDeferredActorSpawnFromClass',args=(w,c,t,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    return gs.call_method('FinishSpawningActor',args=(a,t,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
def audit(w,c):
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ConstraintAudit')
    rows=json.loads((folder/'World.json').read_text(encoding='utf-8-sig'))['constraints']
    return next(r for r in rows if r['component']==c.get_path_name())
def finish(result,error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if ed.get_game_world():level.editor_request_end_play()
    (folder/'BlueprintPIE.json').write_text(json.dumps({'result':result,'error':error,'rows':s['rows']},indent=2))
    print('CONSTRAINT_BLUEPRINT_PIE',result,error)
def tick(_):
    try:
        assert time.monotonic()-s['start']<90,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if s['phase']=='start':
            if t<.8:return
            a=spawn(w,cls,unreal.Transform(location=unreal.Vector(20000,20000,1500)))
            c=a.get_component_by_class(unreal.PhysicsConstraintComponent)
            dm=next(m for m in a.get_components_by_class(unreal.StaticMeshComponent) if m.get_name()=='Dynamic')
            s.update(actor=a,placed=c,dynamic=dm,time=t,phase='placed')
        elif s['phase']=='placed' and t-s['time']>.4:
            row=audit(w,s['placed'])
            assert row['jolt'] and not row['chaos'],row
            assert row['anchor_gap_cm']<.1,row
            s['rows'].append({'placed_in_blueprint':row})
            s['original']=s['dynamic'].get_world_location()
            a=s['actor'];a.set_actor_location(a.get_actor_location()+unreal.Vector(40,0,0),False,True)
            s.update(time=t,phase='move')
        elif s['phase']=='move' and t-s['time']>.4:
            row=audit(w,s['placed'])
            delta=s['dynamic'].get_world_location()-s['original']
            assert abs(delta.x-40)<.5,(delta,row)
            assert row['jolt'] and row['anchor_gap_cm']<.2,row
            s['rows'].append({'moved_anchor':row,'dynamic_delta_x':delta.x})
            s['placed'].break_constraint()
            j=spawn(w,unreal.PhysicsConstraintActor,unreal.Transform(location=s['dynamic'].get_world_location()))
            c=j.constraint_comp;c.set_disable_collision(True)
            for axis in 'xyz':getattr(c,'set_linear_'+axis+'_limit')(unreal.LinearConstraintMotion.LCM_LOCKED,0)
            for axis in ['twist','swing1','swing2']:getattr(c,'set_angular_'+axis+'_limit')(unreal.AngularConstraintMotion.ACM_LOCKED,0)
            c.set_constrained_components(s['dynamic'],'None',None,'None')
            s.update(spawned=c,time=t,phase='runtime')
        elif s['phase']=='runtime' and t-s['time']>.4:
            row=audit(w,s['spawned'])
            assert row['jolt'] and not row['chaos'] and row['anchor_gap_cm']<.1,row
            assert not audit(w,s['placed'])['jolt']
            s['rows'].append({'runtime_world_anchor':row})
            s['spawned'].break_constraint();s.update(time=t,phase='broken')
        elif s['phase']=='broken' and t-s['time']>.1:
            row=audit(w,s['spawned'])
            assert row['broken'] and not row['jolt'] and not row['chaos'],row
            s['rows'].append({'runtime_broken':row})
            finish('passed')
    except Exception:finish('failed',traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
