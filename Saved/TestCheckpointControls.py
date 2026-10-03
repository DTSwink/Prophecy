import builtins,json,pathlib,time,traceback,unreal
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not e.get_game_world()
s=dict(start=time.monotonic(),last=-1,n=0,samples=[])
builtins._checkpoint_controls=s
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CheckpointControls.json').write_text(json.dumps(dict(reason=reason,samples=s['samples'])))
    if e.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('CHECKPOINT_CONTROLS',reason)
def tick(_):
    try:
        if time.monotonic()-s['start']>90:finish('timeout');return
        w=e.get_game_world()
        if not w:return
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['n']+=1;n=s['n']
        if n==10:
            assert a.get_locomotion_walk_checkpoint_speed_threshold()==-1
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            a.set_actor_tick_enabled(False)
            assert a.set_locomotion_policy_blend_times(.2,.3)
            a.set_locomotion_input(unreal.Vector(0,0,0),True,unreal.Vector(1,0,0))
            assert a.set_locomotion_walk_checkpoint_speed_threshold(100)
        if n==50:
            assert a.get_locomotion_checkpoint_weights()[0]>.999
            assert a.get_locomotion_state()[2], 'Walk checkpoint must not turn off run mode'
            a.set_locomotion_walk_checkpoint_speed_threshold(-1)
        if n==90:
            assert a.get_locomotion_checkpoint_weights()[1]>.999
            a.set_locomotion_walk_checkpoint_speed_threshold(250)
            a.set_locomotion_input(unreal.Vector(1,0,0),True,unreal.Vector(1,0,0))
        if n==220:
            assert a.get_locomotion_checkpoint_weights()[1]>.999
            assert a.get_locomotion_state()[0].length()>250
            a.stop_locomotion_input()
        if n==340:
            assert a.get_locomotion_checkpoint_weights()[0]>.999
            assert a.get_locomotion_state()[2]
            a.set_locomotion_policy_blend_times(0,0)
            a.set_locomotion_walk_checkpoint_speed_threshold(-1)
        if n>=12:
            wr=a.get_locomotion_checkpoint_weights();assert wr is not None
            assert -1e-6<=wr[0]<=1.000001 and abs(sum(wr)-1)<1e-6
            v,_,run=a.get_locomotion_state()
            s['samples'].append(dict(n=n,t=t,walk=wr[0],run=wr[1],speed=v.length(),run_mode=run))
        if n>=360:
            assert a.get_locomotion_checkpoint_weights()[1]>.999
            assert any(.05<x['walk']<.95 for x in s['samples'])
            finish('complete')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
