import unreal, pathlib, json, time, traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user PIE'
def library(name):
    return unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.'+name))
reset=library('ProphecyAgentResetLibrary')
damping=library('ProphecyJointDampingLibrary')
profiles=library('ProphecyPhysicalProfileLibrary')
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/ResetPhysicalBaseline.json'
s={'start':time.monotonic(),'frame':0,'phase':'setup','checks':[]}
def read(a):
    return profiles.call_method('PrintPhysicalBoneProfiles',(a,0.,unreal.LinearColor(1,1,1,1)))
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if ed.get_game_world():level.editor_request_end_play()
    out.write_text(json.dumps({'error':error,'checks':s['checks'],'baseline':s.get('base')},indent=2))
    print('RESET_PHYSICS_RESULT', error or 'passed')
def request(w):
    result=reset.call_method('ResetInitialAgents',(w,))
    assert result is not None, 'Reset request rejected'
def tick(_):
    try:
        assert time.monotonic()-s['start']<90,'Timeout'
        w=ed.get_game_world()
        if not w:return
        s['frame']+=1
        if s['phase']=='setup':
            if unreal.GameplayStatics.get_time_seconds(w)<.15:return
            actors=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
            assert actors,'No agents'
            for a in actors:
                unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',(a,'bool debug 1',False))
                a.stop_nn_attack()
                unreal.ProphecyNNDefenseLibrary.stop_nn_defense(a)
                a.stop_locomotion_input()
            s['actors']=actors
            assert reset.call_method('InitializeAgentReset',(w,)) is not None
            # Capture the comparison BEFORE any reset. A post-reset baseline can
            # hide a reset that consistently disables initially implicit drives.
            s['base']={a.get_name():read(a) for a in s['actors']}
            s.update(phase='baseline',at=s['frame'])
            return
        if s['phase']=='baseline' and s['frame']-s['at']>=10:
            assert any(a.is_jolt_physical_animation_enabled() for a in s['actors']),'No live Jolt rig'
            for a in s['actors']:
                a.set_body_magnetization('head',False,9.,8.)
                a.set_physical_feedback_tolerance('head',123.,234.)
                if a.is_jolt_physical_animation_enabled():
                    assert damping.call_method('SetJoltJointAngularDamping',(a,'head',321.)) is not None
                    assert damping.call_method('BlendJoltJointAngularDamping',(a,'head',777.,1.,unreal.ProphecyLocomotionSelection.BOTH,unreal.ProphecyEquipmentSelection.BOTH))
                a.blend_body_magnetization('head',7.,6.,1.)
                a.blend_physical_feedback_tolerance('head',345.,456.,1.)
            assert any(read(a)!=s['base'][a.get_name()] for a in s['actors']),'Mutation did not apply'
            request(w)
            s.update(phase='verify',at=s['frame'])
        elif s['phase']=='verify' and s['frame']-s['at'] in (10,90):
            for a in s['actors']:
                actual=read(a)
                assert actual==s['base'][a.get_name()],(a.get_name(),actual,s['base'][a.get_name()])
            s['checks'].append({'ticks_after_reset':s['frame']-s['at'],'all_agents_profiles_restored':True})
            if s['frame']-s['at']==90:finish()
    except Exception:
        finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('Started bounded reset check in disposable PIE; no asset edits or saves.')
