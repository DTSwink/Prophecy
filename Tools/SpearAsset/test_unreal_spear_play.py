"""Owned unsaved test map: real Blueprint hit admission, travel and release."""
import os,json,pathlib,time,traceback,unreal
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve active Play'
assert all(p.get_name()=='/Game/_mygame/spear/A_Spear' for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
physics=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJoltStandardPhysicsLibrary'))

def prepare():
    world=unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    world.get_world_settings().set_editor_property('default_game_mode',unreal.GameModeBase)
    # Gameplay spawn avoids the editor actor factory's hit-proxy readback,
    # which is invalid in an intentionally headless (-nullrhi) viewport.
    def spawn(cls,position):
        transform=unreal.Transform(location=position)
        statics=unreal.get_default_object(unreal.GameplayStatics.static_class())
        actor=statics.call_method('BeginDeferredActorSpawnFromClass',(world,cls,transform,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
        return statics.call_method('FinishSpawningActor',(actor,transform,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    spawn(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJoltFightSetup'),unreal.Vector())
    spawn(unreal.load_class(None,'/Game/_mygame/blood2/A_DecalManager.A_DecalManager_C'),unreal.Vector())
    cls=unreal.load_class(None,'/Game/_mygame/spear/A_Spear.A_Spear_C')
    cube=unreal.load_asset('/Engine/BasicShapes/Cube')
    for i,mode in enumerate(('forward','withdraw','slash','resistance','flesh')):
        a=spawn(cls,unreal.Vector(i*500,0,0))
        a.set_actor_label('SpearTest_'+mode)
        a.set_editor_property('enable gravity',False)
        mesh=a.get_editor_property('sword');mesh.set_enable_gravity(False)
        root=a.get_editor_property('hilt half length');length=a.get_editor_property('blade length')
        if mode=='flesh':
            victim=spawn(unreal.SkeletalMeshActor,unreal.Vector(i*500+200,0,300))
            victim.set_actor_label('SpearTarget_flesh')
            c=victim.skeletal_mesh_component
            c.set_skeletal_mesh_asset(unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin'))
            c.set_collision_profile_name('PhysicsActor');c.set_simulate_physics(False);c.set_enable_gravity(False)
            target=c.get_socket_location('head')+unreal.Vector(0,0,6)
            a.set_actor_rotation(unreal.MathLibrary.make_rot_from_z(unreal.Vector(1,0,0)),True)
            a.set_actor_location(target-unreal.Vector(root+length+25,0,0),False,True)
            continue
        p=unreal.Vector(i*500,0,500-root-length-25 if mode!='slash' else 500-root-length*.5)
        a.set_actor_location(p,False,True)
        wall=spawn(unreal.StaticMeshActor,unreal.Vector(i*500,107.5 if mode=='slash' else 0,500 if mode=='slash' else 507.5))
        wall.set_actor_label('SpearTarget_'+mode)
        c=wall.static_mesh_component;c.set_static_mesh(cube)
        c.set_world_scale3d(unreal.Vector(1,.15,1) if mode=='slash' else unreal.Vector(1,1,.15))
        c.set_collision_profile_name('BlockAll')
prepare()
s=dict(start=time.monotonic(),world=None,last=None,handle=None,samples=[],started=False,first={},released={},withdrew=False)

def finish(error=None):
    unreal.unregister_slate_post_tick_callback(s['handle']);s['handle']=None
    if s['world'] and ed.get_game_world()==s['world']:le.editor_request_end_play()
    s['world']=None
    (out/'play.json').write_text(json.dumps({'error':error,'first':s['first'],'released':s['released'],'samples':s['samples']},indent=2),encoding='utf-8')

def tick(dt):
    try:
        world=ed.get_game_world()
        if not world:
            if s['world'] or time.monotonic()-s['start']>60:finish('Play ended or failed to start')
            return
        s['world']=world;t=unreal.GameplayStatics.get_time_seconds(world)
        if t==s['last']:return
        s['last']=t
        for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor):
            if a.get_class().get_name()!='A_Spear_C':continue
            mode=a.get_actor_label().removeprefix('SpearTest_');mesh=a.get_editor_property('sword')
            prelaunch=None
            if not s['started']:
                if mode in ('forward','withdraw'):
                    # Apply on the live fixture after PIE duplication, before
                    # collision/admission; never modify an archetype or CDO.
                    unreal.get_default_object(unreal.SystemLibrary.static_class()).call_method('SetVectorPropertyByName',(a,unreal.Name('velocity cut dampings'),unreal.Vector()))
                    d=a.get_editor_property('velocity cut dampings')
                    assert [d.x,d.y,d.z]==[0,0,0]
                v0=physics.call_method('GetPhysicsLinearVelocity',(mesh,unreal.Name('None')))
                prelaunch=[v0.x,v0.y,v0.z]
                vel=unreal.Vector(0,1000,0) if mode=='slash' else mesh.get_up_vector()*1000
                physics.call_method('SetPhysicsLinearVelocity',(mesh,vel,False,unreal.Name('None')))
            cuts=list(a.get_editor_property('cuts'))
            if cuts and mode not in s['first']:s['first'][mode]=t
            if not cuts and mode in s['first'] and mode not in s['released']:s['released'][mode]=t
            pos=mesh.get_world_location();vel=physics.call_method('GetPhysicsLinearVelocity',(mesh,unreal.Name('None')))
            row={'t':t,'mode':mode,'position':[pos.x,pos.y,pos.z],'velocity':[vel.x,vel.y,vel.z],'cuts':len(cuts),'wound':bool(a.get_editor_property('wound NS'))}
            axis=mesh.get_up_vector();row['axis']=[axis.x,axis.y,axis.z]
            row['root']=a.get_editor_property('hilt half length');row['length']=a.get_editor_property('blade length')
            row['rear']=mesh.get_editor_property('static_mesh').get_bounding_box().min.z*mesh.get_world_scale().z
            if prelaunch is not None:row['prelaunch_velocity']=prelaunch
            row['collision_type']=str(mesh.get_collision_object_type())
            material=mesh.get_material(0)
            row['material']=material.get_path_name() if material else None
            if isinstance(material,unreal.MaterialInstanceDynamic):
                row['stain_depth']=material.get_scalar_parameter_value('BladeBloodDepth')
                row['base_color_texture']=material.get_texture_parameter_value('BaseColor').get_path_name()
            if cuts:
                cut=cuts[0]
                row['type']=cut.get_editor_property('typecut_26_E696872E4D78CD342DE03E8254E2D1D5')
                row['matter']=cut.get_editor_property('typematter_15_407254D74A4A8B8B99007DB7AF8B4FA5')
                victim=cut.get_editor_property('victimcomp_8_E920B57A4FEF4892559CA19BB304C19D')
                bone=cut.get_editor_property('bonename_29_18F73D5E41A0314363F49E9FE4D23A1E')
                wound=unreal.MathLibrary.transform_location(victim.get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_WORLD),cut.get_editor_property('localimpact_18_C5A9727B4F3C635ED6CE39A68580BF05'))
                row['wound_position']=[wound.x,wound.y,wound.z]
                row['axial']=unreal.MathLibrary.dot_vector_vector(wound-pos,mesh.get_up_vector())-a.get_editor_property('hilt half length')
                d=a.get_editor_property('velocity cut dampings');row['damping']=[d.x,d.y,d.z]
            s['samples'].append(row)
            if mode=='resistance' and cuts and t-s['first'][mode]>.1 and not s.get('audited'):
                unreal.SystemLibrary.execute_console_command(world,'Prophecy.Jolt.ConstraintAudit A_Spear')
                audit=out.parent/'StandardConstraints/World.json'
                if audit.exists():(out/'play-resistance-joint.json').write_bytes(audit.read_bytes())
                s['audited']=True
            if mode=='withdraw' and cuts and t-s['first'][mode]>.05 and not s['withdrew']:
                s['withdrew']=True
                physics.call_method('SetPhysicsLinearVelocity',(mesh,unreal.Vector(0,0,-1000),False,unreal.Name('None')))
        s['started']=True
        if t>3:finish()
        elif time.monotonic()-s['start']>300:finish('Timed out before three game seconds')
    except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play()
print('Owned spear Play tests queued; no map saved.')
