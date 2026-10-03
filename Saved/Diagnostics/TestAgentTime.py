"""Owned PIE only: rates/window/cadence, special resets, and shared Jolt following.
No Blueprint graph, class default, map edit or save. Test actors are disposable.
"""
import unreal,json,pathlib,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
def lib(name):return unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.'+name))
clock=lib('ProphecyAgentTimeLibrary');root=lib('ProphecyRootPhysicsLibrary')
velocity=lib('ProphecyRootVelocityLibrary');bounds=lib('ProphecyRootPelvisBoundsLibrary')
recovery=lib('ProphecyAttackRecoveryLibrary');temper=lib('ProphecyLowerTemperingLibrary')
limits=lib('ProphecyRootSpeedLimitsLibrary');defense=lib('ProphecyNNDefenseLibrary')
window=lib('ProphecyNNRootWindowLibrary')
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AgentTimePIE.json'
s=dict(start=time.monotonic(),last=-1.,phase='setup',rows=[],ticks=0,actors=[],physical=False)
V=unreal.Vector
def call(obj,name,*args):return obj.call_method(name,tuple(args))
def rate(a):return call(clock,'GetAgentTimeDilation',a)
def setrate(a,r):assert call(clock,'SetAgentTimeDilation',a,r),(a.get_name(),r)
def point(a,bone):return a.get_authored_body_world_target(bone)[2].translation
def finite(a):
    values=a.read_nn_future_world_pose()
    assert values
    for pose in values[:3]:
        if pose and isinstance(pose[0],unreal.Transform):
            assert all(math.isfinite(x) for t in pose for x in (t.translation.x,t.translation.y,t.translation.z))
def finish(result,error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if ed.get_game_world():level.editor_request_end_play()
    out.write_text(json.dumps(dict(result=result,error=error,rows=s['rows']),indent=2))
    print('AGENT_TIME_PIE',result,error)
def magic(a,speed):
    for name in ('SetRootMagicVelocity','SetRootMagicVelocity2','SetRootMagicAngVelocity','SetRootMagicAngVelocity2'):
        assert call(root,name,a,V(speed,0,0) if name=='SetRootMagicVelocity' else V(),False)
def prepare(a,i):
    a.set_editor_property('auto_publish_manual_follower_substep_targets',False)
    a.set_actor_tick_enabled(False)
    call(defense,'StopNNDefense',a);a.stop_nn_attack();a.stop_nn_animation_layer(0)
    a.stop_locomotion_input();assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
    assert call(root,'SetRootSelfBalancing',a,False)
    assert call(bounds,'SetRootPelvisBounds',a,False,20.,None)
    assert call(limits,'SetRootVelocityLimits',a,1000000.,1000000.,False)
    assert call(window,'SetLocomotionRootWindowSmoothing',a,1.,1.,1.)
    normal=unreal.ProphecyRecoverySource.NORMAL
    assert call(recovery,'SetAttackToLocomotionBlend',a,normal,0.,0.,normal,0.,0.,normal,0.,0.)
    assert call(temper,'SetLocomotionLowerBodyTempering',a,False,1.,1.,1.,1.,1.,1.)
    assert call(velocity,'SetRootVelocity',a,V(),False)
    assert call(velocity,'SetRootAngVelocity',a,V(),False)
    assert call(root,'SetLocomotionRootWindowLocation',a,V(1000.,i*400.,a.get_root_low_point().z))
    magic(a,100.)

def begin_measure(t):
    s.update(phase='measure',time=t,ticks=0,initial=[a.get_root_low_point() for a in s['actors']],
        raw=[a.get_locomotion_root_window()[-2][1].translation for a in s['actors']],changes=[0]*3)

def start_special(kind,t):
    a,d=s['actors'][:2]
    for actor in (a,d):
        call(defense,'StopNNDefense',actor);actor.stop_nn_attack();magic(actor,0.)
    facing=a.get_locomotion_state()[1]
    assert call(root,'SetLocomotionRootWindowLocation',d,a.get_root_low_point()+facing*90.)
    setrate(a,2.);setrate(d,.5)
    half=kind=='half'
    assert a.trigger_nn_attack('slashRU',point(d,'head'),half,d),'Attack start'
    assert rate(a)==1.,'Attack failed to reset rate'
    assert not call(clock,'SetAgentTimeDilation',a,2.),'Active attack accepted acceleration'
    if kind in ('parry','dodge'):
        result=call(defense,'StartNNParry' if kind=='parry' else 'StartNNDodge',d,a,3.)
        assert result is not None,(kind,result)
    s.update(phase='special',kind=kind,time=t,ticks=0,seen_defense=False,frames=[])

def tick(_):
    try:
        assert time.monotonic()-s['start']<300,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        if s['phase']=='setup':
            if t<1.:return
            actors=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
            assert len(actors)>=3
            s['actors']=actors[:3]
            for i,a in enumerate(actors):prepare(a,i)
            for a,r in zip(s['actors'],(1.,2.,.5)):setrate(a,r)
            for bad in (0.,-1.,float('nan'),float('inf'),1.e-44):
                assert not call(clock,'SetAgentTimeDilation',s['actors'][0],bad)
            s.update(phase='settle',time=t)
            return
        if s['physical']:
            for a in s['actors']:
                if a.is_jolt_physical_animation_enabled():a.publish_manual_follower_substep_targets(unreal.GameplayStatics.get_world_delta_seconds(w))
        if s['phase']=='settle':
            if t-s['time']>.5:begin_measure(t)
        elif s['phase']=='measure':
            for i,(a,r) in enumerate(zip(s['actors'],(1.,2.,.5))):
                raw=a.get_locomotion_root_window()[-2][1].translation
                if (raw-s['raw'][i]).length()>.001:s['changes'][i]+=1
                s['raw'][i]=raw
                roots,times=call(root,'GetContinuousLocomotionRootWindow',a)[-2:]
                assert (roots[0].translation-a.get_root_low_point()).length()<.001
                assert abs(times[1]-1./30./r)<1.e-6
                observed=a.get_root_velocity()[0].x
                assert abs(observed-100.*r)<.01,(a.get_name(),observed,r,call(root,'GetRootMagicVelocity',a),a.get_locomotion_state())
                finite(a)
            s['ticks']+=1
            if s['ticks']>=120:
                measured=[(a.get_root_low_point()-p).x/(t-s['time']) for a,p in zip(s['actors'],s['initial'])]
                assert all(abs(x-100.*r)<.2 for x,r in zip(measured,(1.,2.,.5))),measured
                # Project currently runs fixed60Hz; record counts without relying
                # on a render/Slate callback for more-than-one-step observations.
                s['rows'].append(dict(stage='rates',rates=[1.,2.,.5],world_speeds=measured,visible_policy_changes=s['changes'],game_ticks=s['ticks']))
                a=s['actors'][1];before=a.read_nn_future_world_pose()[2]
                setrate(a,1.)
                after=a.read_nn_future_world_pose()[2]
                assert max((x.translation-y.translation).length() for x,y in zip(before,after))<.001
                for actor,r in zip(s['actors'],(1.,2.,.5)):
                    setrate(actor,r)
                    assert call(root,'SetRootMagicAngVelocity',actor,V(0,0,20.),False)
                s.update(phase='angular_warm',time=t)
        elif s['phase']=='angular_warm':
            if t-s['time']>.5:
                s.update(phase='angular',time=t,ticks=0,yaws=[a.get_actor_rotation().yaw for a in s['actors']])
        elif s['phase']=='angular':
            s['ticks']+=1
            if s['ticks']>=60:
                angular=[((a.get_actor_rotation().yaw-yaw+180.)%360.-180.)/(t-s['time']) for a,yaw in zip(s['actors'],s['yaws'])]
                assert all(abs(x-20.*r)<.05 for x,r in zip(angular,(1.,2.,.5))),angular
                for actor,r in zip(s['actors'],(1.,2.,.5)):
                    assert abs(actor.get_root_velocity()[0].x-100.*r)<.01,'World momentum rotated with root'
                s['rows'].append(dict(stage='angular',degrees_per_world_second=angular))
                start_special('full',t)
        elif s['phase']=='special':
            a,d=s['actors'][:2];state=a.get_nn_attack_state()
            if state:
                assert rate(a)==1.
                s['frames'].append(state[-1])
            if s['kind'] in ('parry','dodge'):
                status=call(defense,'GetNNDefenseStatus',d)
                if status and status.active:
                    s['seen_defense']=True
                    assert rate(d)==1.,'Defense did not reset multiplier on Armed'
                    assert not call(clock,'SetAgentTimeDilation',d,2.)
            s['ticks']+=1
            if s['ticks']>=150:
                if s['kind'] in ('parry','dodge'):assert s['seen_defense'],(s['kind']+' never activated in fixture',str(state),s['frames'])
                a.stop_nn_attack();call(defense,'StopNNDefense',d)
                assert rate(a)==1.
                if s['seen_defense']:assert rate(d)==1.
                s['rows'].append(dict(stage=s['kind'],stayed_at_one=True,defense_activated=s['seen_defense'],attacker_frames=s['frames']))
                order=['full','half','parry','dodge']
                index=order.index(s['kind'])+1
                if index<len(order):start_special(order[index],t)
                else:
                    for a in s['actors']:
                        setrate(a,1.);magic(a,0.)
                    a=s['actors'][0]
                    a.set_all_physical_feedback_tolerances(1000.,1000.)
                    a.set_all_body_magnetization(True,1.,1.)
                    assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
                    setrate(a,2.);magic(a,100.)
                    s.update(physical=True,phase='physical',time=t,ticks=0,errors=[])
        elif s['phase']=='physical':
            a=s['actors'][0]
            assert a.is_jolt_physical_animation_enabled()
            finite(a)
            target=point(a,'pelvis');mesh=next(c for c in a.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='PhysicalMesh')
            error=(mesh.get_socket_location('pelvis')-target).length()
            assert math.isfinite(error) and error<200.,error
            s['errors'].append(error);s['ticks']+=1
            if s['ticks']>=90:
                s['rows'].append(dict(stage='physical',rate=rate(a),samples=len(s['errors']),max_pelvis_error_cm=max(s['errors']),final_pelvis_error_cm=error))
                finish('passed')
    except Exception:finish('failed',traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
