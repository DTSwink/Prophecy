import unreal,pathlib,json,time
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user PIE'
def library(name):return unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.'+name))
d=library('ProphecyJointDampingLibrary');p=library('ProphecyPhysicalProfileLibrary');lim=library('ProphecyAngularLimitBlendLibrary')
def call(lib,name,*args):return lib.call_method(name,args=args)
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/damping_limits_blend_result.json'
s={'phase':0,'frame':0,'rows':[],'started':time.monotonic()}
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    out.write_text(json.dumps({'error':error,'rows':s['rows']},default=str,indent=2))
def value():
    result=call(d,'GetJoltJointAngularDamping',s['a'],'lowerarm_l')
    assert result is not None,'Damping getter failed'
    return float(result)
def tick(_):
    try:
        assert time.monotonic()-s['started']<75,'timeout'
        w=ed.get_game_world()
        if not w:return
        if s['phase']==0:
            if unreal.GameplayStatics.get_time_seconds(w)<1.0:return
            a=unreal.GameplayStatics.get_player_pawn(w,0);assert isinstance(a,unreal.ProphecyAgent)
            for actor in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
                unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',args=(actor,'bool debug 1',False))
                actor.stop_nn_attack()
            assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
            assert a.enable_jolt_physical_animation()
            s['a']=a
            assert call(d,'SetJoltJointLocomotionDamping',a,'lowerarm_l',20.,40.,60.,80.) is not None
            assert call(p,'SavePhysicalProfileSnapshot',a,'DampingTest')
            assert call(d,'SetJoltJointAngularDamping',a,'lowerarm_l',0.) is not None
            assert value()==0
            assert call(p,'BlendJointAngularDampingToSnapshot',a,'lowerarm_l',1.,'DampingTest')
            s.update(phase=1,frame=0)
            return
        s['frame']+=1;a=s['a']
        if s['phase']==1:
            if s['frame']==30:
                v=value();assert 9.0<=v<=41.0,('midpoint',v);s['rows'].append(['halfway',v])
            if s['frame']>=61:
                v=value();assert 19.99<=v<=80.01,('restored',v)
                text=call(p,'PrintPhysicalBoneProfiles',a,0.,unreal.LinearColor(1,1,1,1));assert '/ D=' in text
                s['rows'].append(['snapshot_restored',v])
                assert call(d,'BlendJoltJointAngularDampingBelow',a,'lowerarm_l',True,0.,0.,unreal.ProphecyLocomotionSelection.BOTH,unreal.ProphecyEquipmentSelection.BOTH)>=2
                assert value()==0
                assert call(p,'BlendJointAngularDampingBelowToSnapshot',a,'lowerarm_l',True,0.,'DampingTest')>=2
                assert value()>0
                assert a.set_use_authored_angular_limits(False)
                assert call(lim,'BlendToAuthoredAngularLimits',a,1.) is not None
                s.update(phase=2,frame=0)
        elif s['phase']==2 and s['frame']>=61:
            s['rows'].append(['limits_blend_survived',s['frame']])
            assert call(lim,'BlendToAuthoredAngularLimits',a,0.) is not None
            assert a.set_use_authored_angular_limits(False)
            assert call(lim,'BlendToAuthoredAngularLimits',a,1.) is not None
            assert a.set_use_authored_angular_limits(False) # explicit setter cancels
            s['rows'].append(['immediate_restore_and_cancellation',True])
            s.update(phase=3,frame=0)
        elif s['phase']==3 and s['frame']>=3:
            finish()
    except Exception as exc:finish(str(exc))
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('Bounded damping snapshot/limit blend PIE check started; changes are PIE-only.')
