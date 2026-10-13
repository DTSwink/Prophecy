"""Owned PIE numerical test; no saved scene/Blueprint mutations."""
import unreal,pathlib,json,time,math,traceback,sys
r=pathlib.Path(unreal.Paths.project_dir()).resolve();out=r/'Saved/Diagnostics/HolsterStrap20261013'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Existing user Play left untouched'
cls=unreal.load_class(None,'/Game/_mygame/assets/holster/Animated/BP_HolsterWithStrap.BP_HolsterWithStrap_C');assert cls
ctype=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyHolsterStrapComponent');assert ctype
s={'world':None,'start':time.monotonic(),'last':-1,'rows':[],'events':[],'still':'--still' in sys.argv,'passive':'--passive' in sys.argv,'settle':'--settle' in sys.argv,'sideways':'--sideways' in sys.argv}
old=unreal.SystemLibrary.get_console_variable_int_value('prophecy.HolsterStrap')
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['callback'])
    if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
    w=ed.get_game_world() or ed.get_editor_world();unreal.SystemLibrary.execute_console_command(w,f'prophecy.HolsterStrap {old}')
    result={k:v for k,v in s.items() if k not in ['world','actor','strap','start','callback','origin']};result['reason']=reason
    (out/'probe.json').write_text(json.dumps(result,separators=(',',':')));print('HOLSTER_STRAP_PROBE',reason)
def pose(t):
    p,q=t.translation,t.rotation;return [p.x,p.y,p.z,q.x,q.y,q.z,q.w]
def tick(_):
    try:
        if time.monotonic()-s['start']>150:return finish('timeout')
        w=ed.get_game_world()
        if not w:
            if s['world']:return finish('ended externally')
            return
        s['world']=w;p=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(p,unreal.ProphecyAgent):return
        n=int(p.get_editor_property('absolute tick debug'))
        if n==s['last']:return
        s['last']=n
        if 'actor' not in s and n>=15:
            tr=unreal.Transform(location=p.get_actor_location()+unreal.Vector(150,0,120),rotation=unreal.Rotator(pitch=90 if s['sideways'] else 0))
            gs=unreal.get_default_object(unreal.GameplayStatics)
            actor=gs.call_method('BeginDeferredActorSpawnFromClass',args=(w,cls,tr,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
            actor=gs.call_method('FinishSpawningActor',args=(actor,tr,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
            assert actor and actor.get_world()==w,'Fixture must exist only in owned PIE'
            c=actor.get_component_by_class(ctype);assert c
            body=c.get_attach_parent()
            body.set_simulate_physics(False)
            body.attach_to_component(actor.root_component,'',unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,False)
            assert body.get_attach_parent()==actor.root_component,'Holster must follow the test actor root'
            # Isolate directional tests from the user's current Blueprint placement.
            # These are the spawned PIE copies, never the asset's templates.
            c.get_attach_parent().set_relative_transform(unreal.Transform(),False,True)
            c.set_relative_transform(unreal.Transform(),False,True)
            s['components']=[{'name':x.get_path_name(),'mesh':str(x.get_skinned_asset()),'bones':x.get_num_bones(),'parent':str(x.get_attach_parent()),'active':x.is_active(),'world':str(x.get_world()),'tick':str(x.get_editor_property('primary_component_tick'))} for x in actor.get_components_by_class(ctype)]
            assert c.get_skinned_asset() and c.get_num_bones()==8,s['components']
            c.max_simulation_distance=100000.
            if s['passive']:c.stiffness=0.;c.damping=10.
            s['profile']={'stiffness':c.stiffness,'damping':c.damping,'max_bend':c.max_bend_angle}
            s.update(actor=actor,strap=c,origin=actor.get_actor_location(),spawn=n)
            unreal.SystemLibrary.execute_console_command(w,'prophecy.HolsterStrap 1')
            c.call_method('SetStrapEnabled',args=(False,))
            s['rest']={b:pose(c.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_COMPONENT)) for b in ['strap_root',*[f'strap_{i:02d}' for i in range(1,6)],'strap_tip']}
        if 'actor' not in s:return
        t=n-s['spawn'];c=s['strap'];a=s['actor']
        if s['settle']:t-=min(600,max(0,t-79))
        assert c.get_owner()==a and c.get_num_bones()==8,'Fixture/component was destroyed during test'
        if t==10:
            s['debug']={'world':str(c.get_world()),'owner':str(c.get_owner()),'anim':str(c.get_anim_instance()),'bone_names':[str(c.get_bone_name(i)) for i in range(c.get_num_bones())],'transform':str(c.get_world_transform())}
            s['debug']['hierarchy']=[{'name':x.get_name(),'parent':str(x.get_attach_parent()),'transform':str(x.get_world_transform())} for x in a.get_components_by_class(unreal.SceneComponent)]
        events=[(5,'enable',lambda:c.call_method('SetStrapEnabled',args=(True,))),
                (80,'manual_off',lambda:c.call_method('SetStrapEnabled',args=(False,))),
                (110,'manual_on',lambda:c.call_method('SetStrapEnabled',args=(True,))),
                (150,'far',lambda:setattr(c,'max_simulation_distance',1.)),
                (185,'near',lambda:setattr(c,'max_simulation_distance',100000.)),
                (220,'global_off',lambda:unreal.SystemLibrary.execute_console_command(w,'prophecy.HolsterStrap 0')),
                (250,'global_on',lambda:unreal.SystemLibrary.execute_console_command(w,'prophecy.HolsterStrap 1')),
                (310,'manual_off_final',lambda:c.call_method('SetStrapEnabled',args=(False,)))]
        for when,label,fn in events:
            if t>=when and label not in [x[1] for x in s['events']]:fn();s['events'].append([t,label])
        offset=unreal.Vector(20*math.sin(t*.11),12*math.sin(t*.07),5*math.cos(t*.09))
        if s['still']:offset=unreal.Vector()
        if t>=280:offset+=unreal.Vector(500,0,0)
        rotation=unreal.Rotator(pitch=(90 if s['sideways'] else 0)+(0 if s['still'] else 10*math.sin(t*.05)),yaw=0 if s['still'] else 30*math.sin(t*.07),roll=0)
        a.set_actor_location_and_rotation(s['origin']+offset,rotation,False,True)
        bones={b:pose(c.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_COMPONENT)) for b in s['rest']}
        row={'tick':n,'t':t,'running':c.call_method('IsStrapSimulating'),'enabled':c.get_editor_property('strap_enabled'),'component_tick':c.is_component_tick_enabled(),'collision':str(c.get_collision_enabled()),'bones':bones}
        assert all(math.isfinite(v) for values in bones.values() for v in values),'Nonfinite strap pose'
        assert c.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION
        s['rows'].append(row)
        if t>=335:return finish('completed')
    except Exception:return finish(traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play();print('HOLSTER_STRAP_PROBE_STARTED')
