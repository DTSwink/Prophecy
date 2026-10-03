"""Transient forearm-band checks through both interpolation modes. No asset edits."""
import builtins,json,pathlib,math,traceback,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/BackwardTurn'
contract=json.loads((pathlib.Path(unreal.Paths.project_content_dir())/'locomotion/NN/prophecy_upper_body_runtime.json').read_text())
lengths=[p[1]*100 for p in contract['arm_limb_lengths_m']]
s=dict(actors=[],last=-1,phase=-1,samples=0,max_error=0)
builtins._forearm_check=s
def pos(t):return [t.translation.x,t.translation.y,t.translation.z]
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    (out/'ForearmClampSmoke.json').write_text(json.dumps(dict(reason=reason,samples=s['samples'],max_excess_cm=s['max_error'])))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('FOREARM_CLAMP_CHECK',reason)
def tick(_):
    try:
        w=ed.get_game_world()
        if not w:return
        now=unreal.GameplayStatics.get_time_seconds(w)
        if now==s['last']:return
        s['last']=now
        if not s['actors']:
            s['actors']=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.get_agent_handle().index in [0,2]]
            assert len(s['actors'])==2
            for i,a in enumerate(s['actors']):
                a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
                a.set_actor_tick_enabled(False)
                a.stop_nn_attack()
                a.set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(0,1,0),1,1)
                a.set_nn_interpolation_mode(unreal.ProphecyNNInterpolationMode.HERMITE_SLERP if i else unreal.ProphecyNNInterpolationMode.CURRENT)
                assert a.set_locomotion_hand_clamp(True,0)
                assert not a.set_locomotion_forearm_clamp(True,-1)
        phase=0 if now<1 else 1
        if phase!=s['phase']:
            for a in s['actors']:assert a.set_locomotion_forearm_clamp(True,phase)
            s['phase']=phase
        for a in s['actors']:
            a.stop_nn_attack()
            p=a.read_nn_future_world_pose()
            if not p or now<.2 or abs(now-1)<.12:continue
            names,future,shown,alpha=p
            ix={str(n):i for i,n in enumerate(names)}
            for side,length in zip(['l','r'],lengths):
                for transforms in [future,shown]:
                    d=math.dist(pos(transforms[ix['hand_'+side]]),pos(transforms[ix['lowerarm_'+side]]))
                    error=max(0,abs(d-length)-phase)
                    s['max_error']=max(s['max_error'],error)
                    assert error<.002,(phase,side,d,length)
                    s['samples']+=1
        if now>=2.2:
            assert s['samples']>100
            for a in s['actors']:assert a.set_locomotion_forearm_clamp(False,1)
            finish('passed')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
