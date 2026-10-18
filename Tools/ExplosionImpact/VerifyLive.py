"""Short owned Play test of the installed receiver on the actual player PHAT.
No asset writes or Blueprint wiring changes. Ends only its own Play session.
"""
import unreal, pathlib, json, time, traceback
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/ExplosionImpact'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
s={'world':None,'start':time.monotonic(),'last':-1,'events':[],'rows':[]}
api=unreal.get_default_object(unreal.load_class(None,'/Script/ProphecyJolt.ProphecyExplosionLibrary'))
has_delegate_wrapper=hasattr(unreal,'ProphecyExplosionImpactCallback')

def received(impact):
    def vec(v):return [v.x,v.y,v.z]
    s['events'].append({'observed_tick':s['last'],'bone':str(impact.bone_name),
        'component':impact.hit_component.get_path_name(),'origin':vec(impact.explosion_origin),
        'point':vec(impact.impact_location),'impulse':vec(impact.impulse)})

def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
    (out/'live.json').write_text(json.dumps({'reason':reason,'delegate_wrapper_available':has_delegate_wrapper,'events':s['events'],'rows':s['rows']},indent=2))
    print('EXPLOSION_IMPACT_LIVE',reason)

def fire(a,w):
    m=a.get_pose_reference_mesh()
    origin=m.get_socket_location('pelvis')+unreal.Vector(100,0,0)
    return api.call_method('StartExplosion',(w,origin,1.,500.,2.,0.))

def tick(_):
    try:
        if time.monotonic()-s['start']>180:return finish('timeout')
        w=ed.get_game_world()
        if not w:
            if s['world']:return finish('Play ended externally')
            return
        if s['world'] is None:s['world']=w
        if w!=s['world']:return finish('Play world changed')
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):
            agents=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            if not agents:return
            a=agents[0]
        n=int(a.get_editor_property('absolute tick debug'))
        if n==s['last']:return
        s['last']=n
        if n<90:return
        if not s.get('prepared'):
            a.set_generate_physical_hit_events(False)
            assert a.enable_jolt_physical_animation()
            assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
            s['prepared']=n
            return
        if not a.is_jolt_physical_animation_enabled():return
        if not has_delegate_wrapper:
            # Newly introduced native delegate types are not wrapped after Live Coding.
            # Focused native tests cover callback/gating; verify actual main-world admission here.
            rcls=unreal.load_class(None,'/Script/ProphecyJolt.ProphecyExplosionReceiverComponent')
            r=a.call_method('AddComponentByClass',(rcls,False,unreal.Transform(),False))
            assert r and not r.is_component_tick_enabled()
            assert not r.get_editor_property('OnExplosionImpact').is_bound()
            affected=fire(a,w)
            assert affected>1,affected
            s['rows'].append({'tick':n,'affected':affected,'receiver':r.get_class().get_path_name(),
                'physical_agent':a.get_path_name(),'simulation':str(a.get_simulation_mode())})
            return finish('passed main Play/admission smoke; callback/cooldown verified by isolated native tests')
        if not s.get('receiver'):
            s['callback']=unreal.ProphecyExplosionImpactCallback(received)
            receiver=api.call_method('BindExplosionImpact',(a,s['callback']))
            assert receiver and not receiver.is_component_tick_enabled()
            assert api.call_method('BindExplosionImpact',(a,s['callback']))==receiver
            s['receiver']=receiver;s['begin']=n
            affected=fire(a,w)
            assert affected>1 and len(s['events'])==1,(affected,s['events'])
            assert s['events'][0]['bone']!='None'
            assert s['events'][0]['component'].startswith(a.get_path_name())
            assert any(abs(v)>0 for v in s['events'][0]['impulse'])
            fire(a,w);assert len(s['events'])==1
            s['rows'].append({'tick':0,'affected':affected,'events':1})
            return
        elapsed=n-s['begin']
        count=fire(a,w)
        s['rows'].append({'tick':elapsed,'affected':count,'events':len(s['events'])})
        assert len(s['events'])==(1 if elapsed<30 else 2),(elapsed,s['events'])
        if elapsed>=30:
            assert elapsed==30,'Missed exact boundary in live sampling; inspect native boundary test'
            assert all(row['affected']>1 for row in s['rows'])
            return finish('passed')
    except Exception:return finish(traceback.format_exc())

s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('EXPLOSION_IMPACT_LIVE_STARTED')
