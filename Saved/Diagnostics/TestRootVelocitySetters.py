"""Bounded owned-PIE check; never edits/saves the user's Blueprint or scene."""
import unreal,json,pathlib,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play session'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootVelocityLibrary'))
magic=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
limits=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootSpeedLimitsLibrary'))
assert lib
s=dict(start=time.monotonic(),rows=[],follow=0,actor=None,last=-1)
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootVelocitySettersPIE.json'
def xyz(v):return [v.x,v.y,v.z]
def near(a,b):return (a-b).length()<.0001
def check(a,name,value,add,linear,yaw):
    root=a.get_actor_transform()
    before=a.read_nn_future_world_pose()[2]
    assert lib.call_method(name,(a,value,add)),name
    actual,angular=a.get_root_velocity()
    assert near(actual,linear),(name,xyz(actual),xyz(linear))
    assert abs(math.degrees(angular.z)-yaw)<.0001,(name,math.degrees(angular.z),yaw)
    assert near(root.translation,a.get_actor_location()),'Velocity setter teleported root'
    assert root.rotation==a.get_actor_transform().rotation,'Velocity setter rotated root'
    after=a.read_nn_future_world_pose()[2]
    assert max((x.translation-y.translation).length() for x,y in zip(before,after))<.000001
    s['rows'].append(dict(node=name,add=add,input=xyz(value),linear=xyz(actual),yaw=math.degrees(angular.z)))
def finish(result,error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if ed.get_game_world():level.editor_request_end_play()
    out.write_text(json.dumps(dict(result=result,error=error,rows=s['rows']),indent=2))
    print('ROOT_VELOCITY_SETTERS',result,error)
def tick(_):
    try:
        assert time.monotonic()-s['start']<120,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last'] or t<.5:return
        s['last']=t
        if s['actor'] is None:
            a=next((a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
                if not a.get_nn_attack_state() and a.read_nn_future_world_pose()),None)
            if a is None:return
            s['actor']=a
            assert limits.call_method('SetRootVelocityLimits',(a,1000000.,1000000.,False))
            assert magic.call_method('SetRootMagicVelocity',(a,unreal.Vector(10,20,3),False))
            assert magic.call_method('SetRootMagicVelocity2',(a,unreal.Vector(2,4,1),False))
            assert magic.call_method('SetRootMagicAngVelocity',(a,unreal.Vector(0,0,7),False))
            assert magic.call_method('SetRootMagicAngVelocity2',(a,unreal.Vector(0,0,3),False))
            current=a.get_root_velocity()[0]
            check(a,'SetRootAngVelocity',unreal.Vector(0,0,90),False,current,100)
            check(a,'SetRootVelocity',unreal.Vector(100,-50,999),False,unreal.Vector(112,-26,4),100)
            check(a,'SetRootVelocity',unreal.Vector(30,10,100),True,unreal.Vector(142,-16,4),100)
            check(a,'SetRootAngVelocity',unreal.Vector(123,456,-30),True,unreal.Vector(142,-16,4),70)
            check(a,'SetRootAngVelocity',unreal.Vector(),True,unreal.Vector(142,-16,4),70)
            check(a,'SetRootAngVelocity',unreal.Vector(),False,unreal.Vector(142,-16,4),10)
            check(a,'SetRootVelocity',unreal.Vector(),False,unreal.Vector(12,24,4),10)
            # Both magic sources survive overwrite and additive operations.
            assert near(magic.call_method('GetRootMagicVelocity',(a,)),unreal.Vector(10,20,3))
            assert near(magic.call_method('GetRootMagicVelocity2',(a,)),unreal.Vector(2,4,1))
            assert near(magic.call_method('GetRootMagicAngVelocity',(a,)),unreal.Vector(0,0,7))
            assert near(magic.call_method('GetRootMagicAngVelocity2',(a,)),unreal.Vector(0,0,3))
            # Large rates use the existing yaw safety cap, never become a no-op.
            assert lib.call_method('SetRootAngVelocity',(a,unreal.Vector(0,0,1000000),False))
            rate=math.degrees(a.get_root_velocity()[1].z)
            assert 5000<rate<5410,rate
            check(a,'SetRootAngVelocity',unreal.Vector(),False,unreal.Vector(12,24,4),10)
        else:
            vel,ang=s['actor'].get_root_velocity()
            assert all(math.isfinite(x) for x in xyz(vel)+xyz(ang))
            s['follow']+=1
            if s['follow']>=6:finish('passed')
    except Exception:finish('failed',traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
