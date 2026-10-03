"""Owned PIE only. Tests exact event-time contracts without editing scene assets."""
import unreal,json,pathlib,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play session'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
for name in ('AddRootOffset','AddRootAngleOffset'):
    assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary:'+name), name
s=dict(start=time.monotonic(),rows=[],phase=-1,last=-1)
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootOffsetsPIE.json'
def distance(a,b):return (a-b).length()
def angle(a,b):return math.degrees(2*math.acos(min(1.,abs(sum(getattr(a,k)*getattr(b,k) for k in ('x','y','z','w'))))))
def roots(a):return lib.call_method('GetContinuousLocomotionRootWindow',(a,))[0]
def capture(a):
    names,future,shown,alpha=a.read_nn_future_world_pose()
    mesh=a.get_pose_reference_mesh()
    return dict(roots=roots(a),raw=a.get_locomotion_root_window()[0],future=future,shown=shown,
        mesh=[mesh.get_socket_transform(n,unreal.RelativeTransformSpace.RTS_WORLD) for n in names],velocity=a.get_root_velocity())
def check(a,delta,yaw):
    before=capture(a)
    ok=lib.call_method('AddRootAngleOffset',(a,yaw)) if yaw else lib.call_method('AddRootOffset',(a,delta))
    assert ok, 'Offset rejected in locomotion'
    after=capture(a)
    row=dict(mode=str(a.get_simulation_mode()),yaw=yaw,delta=[delta.x,delta.y,delta.z])
    for key in ('roots','raw'):
        row[key+'_position_error']=max(distance(x.translation+delta,y.translation) for x,y in zip(before[key],after[key]))
        row[key+'_yaw_error']=max(abs((y.rotation.rotator().yaw-x.rotation.rotator().yaw-yaw+180)%360-180) for x,y in zip(before[key],after[key]))
        assert row[key+'_position_error']<.02,row
        assert row[key+'_yaw_error']<.01,row
    for key in ('future','shown','mesh'):
        row[key+'_position_error']=max(distance(x.translation,y.translation) for x,y in zip(before[key],after[key]))
        row[key+'_angle_error']=max(angle(x.rotation,y.rotation) for x,y in zip(before[key],after[key]))
        assert row[key+'_position_error']<.03,row
        assert row[key+'_angle_error']<.05,row
    row['velocity_error']=max(distance(x,y) for x,y in zip(before['velocity'],after['velocity']))
    assert row['velocity_error']<.01,row
    s['rows'].append(row)
def finish(result,error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if ed.get_game_world():level.editor_request_end_play()
    out.write_text(json.dumps(dict(result=result,error=error,rows=s['rows']),indent=2))
    print('ROOT_OFFSETS',result,error)
def tick(_):
    try:
        assert time.monotonic()-s['start']<180,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last'] or t<.5:return
        s['last']=t
        if s['phase']==-1:
            candidates=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            a=next((a for a in candidates if not a.get_nn_attack_state() and a.read_nn_future_world_pose()),None)
            if not a:return
            s['actor']=a
            assert lib.call_method('SetRootMagicVelocity',(a,unreal.Vector(40,10,0),False))
            assert lib.call_method('SetRootMagicAngVelocity',(a,unreal.Vector(0,0,12),False))
            s['phase']=0
        elif s['phase']==0:
            a=s['actor']
            if a.get_nn_attack_state():return
            check(a,unreal.Vector(12,-7,3),0)
            check(a,unreal.Vector(-12,7,-3),0)
            for yaw in (45,-90,180,-135):check(a,unreal.Vector(),yaw)
            assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            s['phase']=1
        elif s['phase']==1:
            a=s['actor']
            if a.get_nn_attack_state():return
            check(a,unreal.Vector(12,-7,3),0)
            check(a,unreal.Vector(-12,7,-3),0)
            for yaw in (45,-90,180,-135):check(a,unreal.Vector(),yaw)
            assert not lib.call_method('AddRootAngleOffset',(a,float('nan')))
            assert lib.call_method('AddRootAngleOffset',(a,0.))
            assert lib.call_method('AddRootOffset',(a,unreal.Vector()))
            assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
            s['phase']=2
        elif s['phase']==2:
            a=s['actor']
            if a.get_nn_attack_state():return
            check(a,unreal.Vector(12,-7,3),0)
            check(a,unreal.Vector(-12,7,-3),0)
            for yaw in (45,-90,180,-135):check(a,unreal.Vector(),yaw)
            s['phase']=3;s['follow']=0
        else:
            a=s['actor'];names,future,shown,alpha=a.read_nn_future_world_pose()
            assert all(math.isfinite(v) for p in shown for v in (p.translation.x,p.translation.y,p.translation.z))
            s['follow']+=1
            if s['follow']>=6:finish('passed')
    except Exception:finish('failed',traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
