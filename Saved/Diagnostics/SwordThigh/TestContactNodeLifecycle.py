import builtins,json,pathlib,time,traceback,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
s=dict(last=-1,events=[],start=time.monotonic())
builtins._contact_node_lifecycle=s
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordThigh/Isolation/NodeLifecycle.json'
def record(a,w,td,name):
    assert a.is_jolt_physical_animation_enabled(), 'Jolt is inactive at '+name
    p=a.get_physical_body_state('hand_r')[0].translation
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ContactExperiment capture lifecycle_'+name+'_'+str(td)+' at %.9f %.9f %.9f'%(p.x,p.y,p.z))
    s['events'].append(dict(tick=td,name=name,mode=str(a.get_jolt_ccd_mode()),iterations=list(a.get_jolt_solver_iterations()),jolt=a.is_jolt_physical_animation_enabled()))
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    out.write_text(json.dumps(dict(reason=reason,events=s['events']),indent=2))
    if ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('CONTACT_NODE_LIFECYCLE',reason)
def tick(_):
    try:
        if time.monotonic()-s['start']>90:finish('timeout');return
        w=ed.get_game_world()
        if not w:return
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        td=a.get_editor_property('tick debug')
        if td==s['last']:return
        s['last']=td
        C=unreal.ProphecyJoltCCDMode
        if td==10:
            assert a.get_jolt_ccd_mode()==C.PHYSICS_ASSET
            assert tuple(a.get_jolt_solver_iterations())==(0,0)
            s['others']=[b for b in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if b!=a]
            a.set_jolt_ccd_mode(C.CONTINUOUS);a.set_jolt_solver_iterations(10,4)
        if td==11:record(a,w,td,'continuous')
        if td==20:a.set_jolt_ccd_mode(C.DISCRETE)
        if td==21:record(a,w,td,'discrete')
        if td==30:a.set_jolt_ccd_mode(C.PHYSICS_ASSET)
        if td==31:record(a,w,td,'authored')
        if td==40:a.set_jolt_ccd_mode(C.CONTINUOUS);assert a.set_sword_simulated(True)
        if td==50:record(a,w,td,'physical_sword');assert a.set_sword_simulated(False)
        if td==60:record(a,w,td,'reattached');assert a.drop_sword()
        if td==70:record(a,w,td,'dropped');assert a.equip_sword(False)
        if td==80:record(a,w,td,'reequipped');a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
        if td==90:
            assert a.get_jolt_ccd_mode()==C.CONTINUOUS
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.HALF_SIM)
        if td==100:a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
        if td==110:record(a,w,td,'readmitted');a.disable_jolt_physical_animation()
        if td==120:
            assert a.get_jolt_ccd_mode()==C.CONTINUOUS and tuple(a.get_jolt_solver_iterations())==(10,4)
            assert a.enable_jolt_physical_animation(), 'Backend re-admission failed'
        if td==130:record(a,w,td,'backend_roundtrip');a.set_jolt_ccd_mode(C.PHYSICS_ASSET)
        if td==140:
            record(a,w,td,'reset_after_roundtrip')
            a.set_jolt_solver_iterations(-1,4);a.set_jolt_solver_iterations(10,129)
            assert tuple(a.get_jolt_solver_iterations())==(10,4)
            a.set_jolt_joint_limit_prediction_enabled(True)
            a.set_physical_joint_angular_limits('hand_r',unreal.AngularConstraintMotion.ACM_LIMITED,45,unreal.AngularConstraintMotion.ACM_LIMITED,45,unreal.AngularConstraintMotion.ACM_FREE,0)
        if td==150:record(a,w,td,'limited');a.set_jolt_joint_limit_prediction_enabled(False)
        if td==160:record(a,w,td,'unwrapped');a.set_jolt_joint_limit_prediction_enabled(True)
        if td==170:record(a,w,td,'rewrapped');a.set_jolt_solver_iterations(0,0)
        if td==180:
            record(a,w,td,'defaults')
            for b in s['others']:
                assert b.get_jolt_ccd_mode()==C.PHYSICS_ASSET and tuple(b.get_jolt_solver_iterations())==(0,0)
            finish('complete')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
