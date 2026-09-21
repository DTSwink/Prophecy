import unreal, pathlib, json, time, traceback
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert not ed.get_game_world(), 'Stop PIE before this fixture'
folder = pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/StandardConstraints'
folder.mkdir(parents=True,exist_ok=True)
s = {'start':time.monotonic(), 'phase':'start', 'rows':[], 'editor':[], 'selection':list(actors.get_selected_level_actors())}
cube = unreal.load_asset('/Engine/BasicShapes/Cube')
tag = 'CodexConstraintFixture'

def configure_mesh(a,dynamic):
    m=a.static_mesh_component
    m.set_mobility(unreal.ComponentMobility.MOVABLE if dynamic else unreal.ComponentMobility.STATIC)
    m.set_static_mesh(cube)
    m.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    m.set_collision_object_type(unreal.CollisionChannel.ECC_PHYSICS_BODY if dynamic else unreal.CollisionChannel.ECC_WORLD_STATIC)
    m.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_BLOCK)
    m.set_enable_gravity(False)
    if dynamic:
        m.set_mass_override_in_kg('None',2,True)
        m.set_simulate_physics(True)
    return m

def configure_joint(c,a,b):
    c.set_disable_collision(True)
    c.set_linear_x_limit(unreal.LinearConstraintMotion.LCM_LOCKED,0)
    c.set_linear_y_limit(unreal.LinearConstraintMotion.LCM_LOCKED,0)
    c.set_linear_z_limit(unreal.LinearConstraintMotion.LCM_LOCKED,0)
    c.set_angular_twist_limit(unreal.AngularConstraintMotion.ACM_LOCKED,0)
    c.set_angular_swing1_limit(unreal.AngularConstraintMotion.ACM_LOCKED,0)
    c.set_angular_swing2_limit(unreal.AngularConstraintMotion.ACM_LOCKED,0)
    c.set_constrained_components(a,'None',b,'None')

try:
    for cls, pos in [(unreal.StaticMeshActor,(10000,10000,1500)),(unreal.StaticMeshActor,(10150,10000,1500)),(unreal.PhysicsConstraintActor,(10075,10000,1500))]:
        a=actors.spawn_actor_from_class(cls,unreal.Vector(*pos),transient=True)
        assert a
        a.tags=list(a.tags)+[tag]
        s['editor'].append(a)
    anchor,dynamic,joint=s['editor']
    am,dm=configure_mesh(anchor,False),configure_mesh(dynamic,True)
    c=joint.constraint_comp
    c.set_editor_property('constraint_actor1',dynamic)
    c.set_editor_property('constraint_actor2',anchor)
    configure_joint(c,dm,am)
except Exception:
    for a in s['editor']: actors.destroy_actor(a)
    actors.set_selected_level_actors(s['selection'])
    raise

def audit(w):
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ConstraintAudit')
    return json.loads((folder/'World.json').read_text(encoding='utf-8-sig'))['constraints']

def finish(result,error=''):
    s['result']=result;s['error']=error;s['phase']='cleanup'
    if ed.get_game_world(): level.editor_request_end_play()

def tick(_):
    try:
        w=ed.get_game_world()
        if s['phase']=='cleanup':
            if w:return
            for a in s['editor']: actors.destroy_actor(a)
            actors.set_selected_level_actors(s['selection'])
            unreal.unregister_slate_post_tick_callback(s['cb'])
            (folder/'PIE.json').write_text(json.dumps({k:s[k] for k in ['result','error','rows']},indent=2))
            print('STANDARD_CONSTRAINT_PIE',s['result'],s['error'])
            return
        assert time.monotonic()-s['start']<90,'Timeout'
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if s['phase']=='start':
            if t<.8:return
            found=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.PhysicsConstraintActor) if a.actor_has_tag(tag)]
            assert len(found)==1,'Placed constraint was not duplicated into PIE'
            s['placed']=found[0].constraint_comp
            rows=audit(w);row=next(r for r in rows if r['component']==s['placed'].get_path_name())
            assert row['jolt'] and not row['chaos'],row
            assert row['anchor_gap_cm']<.1,row
            s['rows'].append({'placed':row})
            gs=unreal.get_default_object(unreal.GameplayStatics)
            trans=unreal.Transform(location=unreal.Vector(10200,10000,1700))
            a=gs.call_method('BeginDeferredActorSpawnFromClass',args=(w,unreal.StaticMeshActor,trans,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
            dm=configure_mesh(a,True)
            gs.call_method('FinishSpawningActor',args=(a,trans,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
            j=gs.call_method('BeginDeferredActorSpawnFromClass',args=(w,unreal.PhysicsConstraintActor,trans,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
            gs.call_method('FinishSpawningActor',args=(j,trans,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
            configure_joint(j.constraint_comp,dm,None)
            s['spawned']=j.constraint_comp;s['spawned_mesh']=dm;s['time']=t;s['phase']='runtime'
        elif s['phase']=='runtime' and t-s['time']>.5:
            rows=audit(w);row=next(r for r in rows if r['component']==s['spawned'].get_path_name())
            assert row['jolt'] and not row['chaos'],row
            assert row['anchor_gap_cm']<.1,row
            s['rows'].append({'runtime_world_anchor':row})
            s['spawned'].break_constraint();s['time']=t;s['phase']='broken'
        elif s['phase']=='broken' and t-s['time']>.1:
            rows=audit(w);row=next(r for r in rows if r['component']==s['spawned'].get_path_name())
            assert row['broken'] and not row['jolt'] and not row['chaos'],row
            s['rows'].append({'runtime_broken':row})
            finish('passed')
    except Exception:finish('failed',traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
