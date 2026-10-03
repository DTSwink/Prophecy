import unreal, json, pathlib, time, traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'Do not interrupt user Play'
api=unreal.ProphecyFootColliderLibrary
print('NODE',api.set_foot_collider_front_trim.__doc__)
s={'phase':0,'start':time.monotonic(),'rows':[],'frames':0}
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FootColliderTrim-live.json'
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    out.write_text(json.dumps(dict(result='failed' if error else 'passed',error=error,rows=s['rows']),indent=2))
    if ed.get_game_world():level.editor_request_end_play()
    print('FOOT_TRIM_LIVE',error or 'passed')
def tick(_):
    try:
        assert time.monotonic()-s['start']<120,'Timeout'
        w=ed.get_game_world()
        if not w:return
        s['frames']+=1
        if unreal.GameplayStatics.get_time_seconds(w)<.5:return
        if s['phase']==0:
            a=unreal.GameplayStatics.get_player_pawn(w,0)
            assert isinstance(a,unreal.ProphecyAgent)
            s['a']=a
            a.stop_nn_attack()
            assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
            assert a.enable_jolt_physical_animation()
            s['phase']=1
        elif s['phase']==1 and s['a'].is_jolt_physical_animation_enabled():
            a=s['a']; mesh=a.get_pose_reference_mesh()
            before=[str(mesh.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in ('foot_l','foot_r','calf_l','calf_r')]
            for value in (0.,5.,3.,0.,5.):
                result=api.set_foot_collider_front_trim(a,value)
                s['rows'].append(dict(trim_cm=value,result=str(result)))
                assert result is not None,(value,result)
            after=[str(mesh.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in ('foot_l','foot_r','calf_l','calf_r')]
            assert before==after,'Synchronous shape-only operation changed rendered pose'
            assert api.set_foot_collider_front_trim(a,10000.) is None,'Oversized trim must fail'
            assert api.set_foot_collider_front_trim(a,-1.) is None,'Negative trim must fail'
            assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            s['phase']=2
        elif s['phase']==2:
            a=s['a']
            assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
            assert a.enable_jolt_physical_animation()
            s['phase']=3;s['admission_frame']=s['frames']
        elif s['phase']==3 and s['a'].is_jolt_physical_animation_enabled() and s['frames']>s['admission_frame']+4:
            a=s['a']
            assert api.set_foot_collider_front_trim(a,0.) is not None
            s['rows'].append(dict(recreated_rig_healthy=True,restored=True,pose_unchanged_on_call=True))
            finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
