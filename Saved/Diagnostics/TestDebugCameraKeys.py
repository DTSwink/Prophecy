import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user PIE'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.DebugCamera.InstallInput')
s={'start':time.monotonic(),'frame':0,'phase':'start','checks':[]}
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if ed.get_game_world():level.editor_request_end_play()
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/DebugCameraKeys.json').write_text(json.dumps({'error':error,'checks':s['checks']},indent=2))
    print('DEBUG_CAMERA_KEYS',error or 'passed')
def command(w,text,pc=None):unreal.SystemLibrary.execute_console_command(w,text,pc)
def tick(_):
    try:
        assert time.monotonic()-s['start']<60,'Timeout'
        w=ed.get_game_world()
        if not w:return
        s['frame']+=1
        if s['phase']=='start':
            if unreal.GameplayStatics.get_time_seconds(w)<.5:return
            pc=unreal.GameplayStatics.get_player_controller(w,0)
            a=unreal.GameplayStatics.get_player_pawn(w,0)
            for actor in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
                unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',(actor,'bool debug 1',False))
                actor.stop_nn_attack();actor.stop_locomotion_input()
            assert a.get_held_sword(),'Missing starting sword'
            s.update(pc=pc,agent=a,phase='enter',at=s['frame'])
            command(w,'ToggleDebugCamera',pc)
        elif s['phase']=='enter' and s['frame']-s['at']>=3:
            ds=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.DebugCameraController)
            assert len(ds)==1,[x.get_name() for x in ds]
            d=ds[0]
            assert d.get_class().get_name()=='ProphecyDebugCameraController',d.get_class().get_name()
            s.update(debug=d,phase='drop',at=s['frame'])
            command(w,'Prophecy.Sword.DebugDropKey press')
        elif s['phase']=='drop' and s['frame']-s['at']>=3:
            command(w,'Prophecy.Sword.DebugDropKey release')
            assert not s['agent'].get_held_sword(),'Existing Right Shift key did not drop sword in debug camera'
            s['checks'].append('Existing Blueprint key executed on original agent in debug camera')
            command(w,'ToggleDebugCamera',s['debug'])
            command(w,'ToggleDebugCamera',s['pc'])
            s.update(phase='reenter',at=s['frame'])
        elif s['phase']=='reenter' and s['frame']-s['at']>=3:
            command(w,'Prophecy.Sword.DebugDropKey press')
            s.update(phase='equip',at=s['frame'])
        elif s['phase']=='equip' and s['frame']-s['at']>=3:
            command(w,'Prophecy.Sword.DebugDropKey release')
            assert s['agent'].get_held_sword(),'Repeated entry did not preserve FlipFlop state / duplicate key delivery'
            s['checks'].append('Re-entry key restored sword once, preserving Blueprint FlipFlop')
            command(w,'ToggleDebugCamera',s['debug'])
            s.update(phase='normal',at=s['frame'])
        elif s['phase']=='normal' and s['frame']-s['at']>=3:
            command(w,'Prophecy.Sword.DebugDropKey press')
            s.update(phase='normal_check',at=s['frame'])
        elif s['phase']=='normal_check' and s['frame']-s['at']>=3:
            command(w,'Prophecy.Sword.DebugDropKey release')
            assert not s['agent'].get_held_sword(),'Normal input failed after debug camera'
            s['checks'].append('Original normal-play key still works after exit')
            finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('Started brief debug-camera key lifecycle check; original Blueprint remains unchanged.')
