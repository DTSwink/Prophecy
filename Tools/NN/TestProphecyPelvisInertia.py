"""Transient testNN correctness check. Does not save assets, change checkpoints or benchmark."""
import builtins, json, math, pathlib, time, traceback, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyPelvisInertiaLibrary'))
root=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
smooth=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNRootWindowLibrary'))
s=dict(start=time.monotonic(),n=0,last=-1,coast=[],physical_samples=0,events=[])
builtins._pelvis_inertia_test=s
def set_(a,on,h=1.,v=1.,y=1.,p=1.,body=False):
    return lib.call_method('SetPelvisInertia',(a,on,h,v,y,p,body))
def xyz(v): return [v.x,v.y,v.z]
def qlog(q):
    values=[q.x,q.y,q.z]; w=q.w
    if w<0: values=[-x for x in values]; w=-w
    length=math.sqrt(sum(x*x for x in values))
    factor=2*math.atan2(length,w)/length if length>1e-12 else 2.
    return [x*factor for x in values]
def qdelta(a,b):
    # world rotation difference: a * inverse(b)
    x,y,z,w=a.x,a.y,a.z,a.w; u,v,t,k=-b.x,-b.y,-b.z,b.w
    return unreal.Quat(w*u+x*k+y*t-z*v,w*v-x*t+y*k+z*u,w*t+x*v-y*u+z*k,w*k-x*u-y*v-z*t)
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/PelvisInertia.json').write_text(json.dumps(
        dict(reason=reason,coast=s['coast'],physical_samples=s['physical_samples'],events=s['events']),indent=2),encoding='utf-8')
    if ed.get_game_world(): unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('PELVIS_INERTIA',reason)
def tick(_):
    try:
        if time.monotonic()-s['start']>180: finish('timeout'); return
        w=ed.get_game_world()
        if not w:return
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        now=unreal.GameplayStatics.get_time_seconds(w)
        if now==s['last']:return
        s['last']=now;s['n']+=1;n=s['n']
        if n==10:
            assert lib.call_method('GetPelvisInertia',(a,))==(False,1.,1.,1.,1.,False)
            a.set_actor_tick_enabled(False); a.stop_nn_attack()
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            a.disable_jolt_physical_animation()
            root.call_method('SetRootSelfBalancing',(a,False,60.,.05,2.,1.,30.,0.))
            smooth.call_method('SetLocomotionRootWindowSmoothing',(a,1.,1.,1.))
            a.set_locomotion_input(unreal.Vector(),False,unreal.Vector(),1.,0.)
            assert set_(a,True)
            s['events'].append('Default settings and enabled all-one accepted')
        if n==40:
            assert set_(a,True,0.,0.,0.,0.,True) # Kinematic must still use target path.
        if 50<=n<=180:
            prev,cur,shown,alpha=a.get_authored_body_world_target('pelvis')
            dt=a.get_nn_pose_data_source()[1]
            linear=[x/dt for x in xyz(cur.translation-prev.translation)]
            angular=[x/dt for x in qlog(qdelta(cur.rotation,prev.rotation))]
            s['coast'].append(dict(n=n,linear=linear,angular=angular,root=xyz(a.get_root_low_point())))
            if len(s['coast'])>1:
                assert math.dist(linear,s['coast'][0]['linear'])<.02,('Linear world coast',linear,s['coast'][0])
                assert math.dist(angular,s['coast'][0]['angular'])<.0002,('Angular world coast',angular,s['coast'][0])
        if n==80:
            a.set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(),1.,0.)
        if n==180:
            assert math.dist(s['coast'][0]['root'],s['coast'][-1]['root'])>1.,'Root must move during world-space check'
            assert set_(a,True) # restore original target before physical admission
            a.set_locomotion_input(unreal.Vector(),False,unreal.Vector(),1.,0.)
        if n==190:
            assert a.enable_jolt_physical_animation()
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
            assert set_(a,True,.2,.3,.4,.5,True)
            s['events'].append('World coast preserved while root moved; entered Jolt Sim body mode')
        if 200<=n<=370:
            a.publish_manual_follower_substep_targets(1./60.)
            result=a.get_physical_body_state('pelvis')
            assert result, 'Pelvis physical readback'
            pose,linear,angular,sim=result
            assert sim
            assert all(math.isfinite(x) for x in xyz(pose.translation)+xyz(linear)+xyz(angular))
            s['physical_samples']+=1
        if n==250:
            a.disable_jolt_physical_animation()
            assert a.get_simulation_mode()==unreal.ProphecyAgentSimulationMode.PHYSICAL
            s['events'].append('Chaos Sim mode preserved with same inertia settings')
        if n==310:
            assert a.enable_jolt_physical_animation()
            s['events'].append('Returned to Jolt with same inertia settings')
        if n==380:
            assert set_(a,False,.2,.3,.4,.5,True)
            assert not lib.call_method('GetPelvisInertia',(a,))[0]
            assert not set_(a,True,-1.,1.,1.,1.)
            s['events'].append('Disable and invalid-input rejection verified')
            finish('passed')
    except Exception: finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
