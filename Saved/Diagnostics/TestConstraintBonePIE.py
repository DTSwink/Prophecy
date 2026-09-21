import unreal,pathlib,json,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/StandardConstraints'
folder.mkdir(parents=True,exist_ok=True)
s={'start':time.monotonic(),'phase':'start','rows':[]}
gs=unreal.get_default_object(unreal.GameplayStatics)
def spawn(w,c,t):
    a=gs.call_method('BeginDeferredActorSpawnFromClass',args=(w,c,t,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    return gs.call_method('FinishSpawningActor',args=(a,t,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
def audit(w,c):
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ConstraintAudit '+c.get_owner().get_name())
    return next(r for r in json.loads((folder/'World.json').read_text(encoding='utf-8-sig'))['constraints'] if r['component']==c.get_path_name())
def finish(result,error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if ed.get_game_world():level.editor_request_end_play()
    (folder/'BonePIE.json').write_text(json.dumps(dict(result=result,error=error,rows=s['rows']),indent=2))
    print('CONSTRAINT_BONE_PIE',result,error)
def tick(_):
    try:
        assert time.monotonic()-s['start']<90,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if s['phase']=='start':
            if t<.8:return
            a=unreal.GameplayStatics.get_player_pawn(w,0)
            assert a.is_jolt_physical_animation_enabled(),'Player must be physically simulated by Jolt'
            mesh=a.get_pose_reference_mesh();body=a.get_physical_body_state('hand_r');assert body
            transform=body[0]
            cube=spawn(w,unreal.StaticMeshActor,unreal.Transform(location=transform.translation))
            m=cube.static_mesh_component;m.set_mobility(unreal.ComponentMobility.MOVABLE)
            m.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube.Cube'))
            m.set_world_scale3d(unreal.Vector(.05,.05,.05))
            m.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
            m.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_IGNORE)
            m.set_simulate_physics(True);m.set_mass_override_in_kg('None',.01,True)
            s.update(agent=a,mesh=mesh,cube=cube,dynamic=m,phase='admit',time=t)
        elif s['phase']=='admit' and t-s['time']>.1:
            # Frame creation uses the current actual hand; retain cube offset.
            body=s['agent'].get_physical_body_state('hand_r');assert body
            c=spawn(w,unreal.PhysicsConstraintActor,unreal.Transform(location=body[0].translation)).constraint_comp
            for axis in 'xyz':getattr(c,'set_linear_'+axis+'_limit')(unreal.LinearConstraintMotion.LCM_LOCKED,0)
            for axis in ['twist','swing1','swing2']:getattr(c,'set_angular_'+axis+'_limit')(unreal.AngularConstraintMotion.ACM_LOCKED,0)
            c.set_disable_collision(True)
            c.set_constrained_components(s['mesh'],'hand_r',s['dynamic'],'None')
            s.update(joint=c,phase='sample',time=t)
        elif s['phase']=='sample' and t-s['time']>.15:
            row=audit(w,s['joint']);assert row['jolt'] and not row['chaos'],row
            assert row['anchor_gap_cm']<1,row
            s['rows'].append(row)
            if len(s['rows'])<12:return
            s['joint'].break_constraint();s.update(phase='broken',time=t)
        elif s['phase']=='broken' and t-s['time']>.1:
            row=audit(w,s['joint']);assert row['broken'] and not row['jolt'] and not row['chaos'],row
            s['rows'].append(row);finish('passed')
    except Exception:finish('failed',traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
