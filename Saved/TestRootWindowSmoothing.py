import builtins,json,pathlib,time,traceback,math,unreal
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not e.get_game_world()
class L:
    cdo=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNRootWindowLibrary'))
    @staticmethod
    def get_locomotion_root_window_smoothing(a):
        return L.cdo.call_method('GetLocomotionRootWindowSmoothing',(a,))
    @staticmethod
    def set_locomotion_root_window_smoothing(a,d,r,o):
        return L.cdo.call_method('SetLocomotionRootWindowSmoothing',(a,d,r,o))
unreal.SystemLibrary.execute_console_command(e.get_editor_world(),'Automation RunTests Prophecy.NN.RootWindow.IndependentFactors')
s=dict(start=time.monotonic(),n=0,last=-1,samples=[],max_offset_error=0.,max_yaw_error=0.)
builtins._root_window_test=s
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    data={k:v for k,v in s.items() if k not in ['cb','seed','start','last']}
    data['reason']=reason
    (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootWindowSmoothing.json').write_text(json.dumps(data))
    if e.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('ROOT_WINDOW_SMOOTHING',reason)
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
            assert tuple(L.get_locomotion_root_window_smoothing(a))==(1.,1.,1.)
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            a.set_actor_tick_enabled(False)
            a.set_locomotion_input(unreal.Vector(1,0,0),True,unreal.Vector(1,0,0))
        if n<12:return
        roots,times=a.get_locomotion_root_window()
        assert len(roots)==10 and times[1]==0
        origin=roots[1].translation
        if n==100:
            s['seed']=[((x.translation-origin),x.rotation.rotator().yaw) for x in roots[2:]]
            assert L.set_locomotion_root_window_smoothing(a,0,0,0)
            assert not L.set_locomotion_root_window_smoothing(a,-1,0,0)
            assert tuple(L.get_locomotion_root_window_smoothing(a))==(0.,0.,0.)
            a.set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(0,1,0))
        if 104<=n<=180:
            for root,(offset,yaw) in zip(roots[2:],s['seed']):
                d=(root.translation-origin-offset).length()
                r=abs((root.rotation.rotator().yaw-yaw+180)%360-180)
                s['max_offset_error']=max(s['max_offset_error'],d)
                s['max_yaw_error']=max(s['max_yaw_error'],r)
                assert d<.02 and r<.002, (n,d,r)
            s['samples'].append([n,origin.x,origin.y,roots[1].rotation.rotator().yaw])
        if n==181:
            assert L.set_locomotion_root_window_smoothing(a,.2,.3,.4)
        if n==220:
            assert L.set_locomotion_root_window_smoothing(a,1,1,1)
            a.set_locomotion_input(unreal.Vector(-1,0,0),True,unreal.Vector(-1,0,0))
        if n>=260:
            assert tuple(L.get_locomotion_root_window_smoothing(a))==(1.,1.,1.)
            first,last=s['samples'][0],s['samples'][-1]
            assert math.hypot(last[1]-first[1],last[2]-first[2])>100, 'Present root must keep moving'
            assert abs((last[3]-first[3]+180)%360-180)>20, 'Present root orientation must keep turning'
            finish('complete')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
