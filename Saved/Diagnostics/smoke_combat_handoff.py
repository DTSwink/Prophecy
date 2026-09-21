import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Leave user PIE untouched'
s={'start':time.monotonic(),'stage':0,'report':{}}
def v(x):return [x.x,x.y,x.z]
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb']);level.editor_request_end_play()
    s['report']['error']=error
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/CombatHandoffSmoke.json').write_text(json.dumps(s['report'],indent=2))
    print('COMBAT_HANDOFF',json.dumps(s['report']))
def tick(dt):
    try:
        if time.monotonic()-s['start']>90:raise RuntimeError('timeout')
        w=ed.get_game_world()
        if not w:return
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not a or not a.has_valid_agent_handle():return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if s['stage']==0 and t>=.5:
            a.set_actor_tick_enabled(False)
            p=unreal.ProphecyRootPhysicsLibrary
            lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
            s['report']['default_run_threshold']=lib.call_method('GetLocomotionAutoRunSpeedThreshold',(a,))
            assert lib.call_method('SetLocomotionAutoRunSpeedThreshold',(a,100.))
            s['report']['native_ccd_mode']=str(a.get_jolt_ccd_mode())
            a.set_locomotion_policy_blend_times(0,0)
            a.stop_locomotion_input()
            p.set_root_magic_velocity(a,unreal.Vector(300,0,0))
            s['stage']=1;s['at']=t
        elif s['stage']==1 and t-s['at']>=.2:
            p=unreal.ProphecyRootPhysicsLibrary
            s['report']['weights']=str(a.get_locomotion_checkpoint_weights())
            cube=next(c for c in a.get_components_by_class(unreal.StaticMeshComponent) if 'magic' in c.get_name().lower())
            unreal.ProphecyRootPelvisBoundsLibrary.set_root_pelvis_bounds(a,True,20,cube)
            root=a.get_root_low_point()
            assert a.trigger_nn_attack('hookl',root+unreal.Vector(0,80,150))
            cube.set_world_location(root+unreal.Vector(100,-75,95),False,True)
            p.set_root_magic_velocity(a,unreal.Vector(1000,500,0));p.set_root_magic_velocity2(a,unreal.Vector(12,34,0))
            s['report']['stopped']=a.stop_nn_attack()
            delta=cube.get_world_location()-a.get_root_low_point()
            s['report']['cube_delta_after_stop']=v(delta)
            s['report']['magic1']=v(p.get_root_magic_velocity(a));s['report']['magic2']=v(p.get_root_magic_velocity2(a))
            assert abs(delta.x)<.001 and abs(delta.y)<.001
            assert all(abs(x)<.001 for x in v(p.get_root_magic_velocity(a)))
            s['stage']=2
            finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
