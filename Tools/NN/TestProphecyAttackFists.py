"""PIE-only fist lifecycle / live mesh regression. Ends PIE; saves no assets."""
import json
import math
import traceback
from pathlib import Path
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world, 'Start testNN PIE first'
agent = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent)
             if a.has_valid_agent_handle() and a.get_editor_property('manual_nn_pose_application'))
agent.set_actor_tick_enabled(False)
agent.call_method('StopNNAttack')
unreal.SystemLibrary.execute_console_command(world,'ke '+agent.get_path_name()+' SetSimulationMode Kinematic')
mesh = agent.get_pose_reference_mesh()
mesh.set_editor_property('enable_update_rate_optimizations',False)
mesh.set_editor_property('visibility_based_anim_tick_option',unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
clip = unreal.load_asset('/Game/_mygame/closed_fist')
ext = unreal.AnimPoseExtensions
closed_pose = ext.get_anim_pose_at_time(clip,0,unreal.AnimPoseEvaluationOptions(evaluation_type=unreal.AnimDataEvalType.RAW,should_retarget=False))
modifier = unreal.SkeletonModifier()
assert modifier.set_skeletal_mesh(mesh.get_skeletal_mesh_asset())
names = [str(n) for n in modifier.get_all_bone_names() if str(n).split('_')[0] in ('index','middle','pinky','ring','thumb') and str(n).endswith(('_l','_r'))]
assert len(names)==38
opens = {n:modifier.get_bone_transform(n,False) for n in names}
closes = {n:ext.get_bone_pose(closed_pose,n,unreal.AnimPoseSpaces.LOCAL) for n in names}
parents = {n:str(modifier.get_parent_name(n)) for n in names}
state = {'handle':None,'phase':-1,'start':0.,'from':[0.,0.],'target':[0.,0.], 'duration':0.,'rows':[], 'max_position_cm':0.,'max_angle_deg':0.,'max_scale':0.,'max_level_error':0.}
output = Path(unreal.Paths.project_saved_dir()).resolve()/'AttackFists/runtime_audit.json'

def settings(left=1.,right=1.,start=.4,end=1.):
    value=agent.call_method('GetAttackFistSettings',args=(unreal.Name('test_defaults'),))
    value.set_editor_properties({'LeftClosedLevel':left,'RightClosedLevel':right,'ClosingStartSeconds':start,'OpeningEndSeconds':end})
    return value

defaults = agent.call_method('GetAttackFistSettings',args=(unreal.Name('jabR'),))
assert max(abs(a-b) for a,b in zip([defaults.get_editor_property(n) for n in ('LeftClosedLevel','RightClosedLevel','ClosingStartSeconds','OpeningEndSeconds')],[1.,1.,.4,1.]))<1e-6

def levels(): return list(agent.call_method('GetFistClosedLevels'))
def now(): return unreal.GameplayStatics.get_time_seconds(world)
def xyz(v): return [v.x,v.y,v.z]
def qnorm(q):
    v=[q.x,q.y,q.z,q.w]; l=math.sqrt(sum(x*x for x in v)); return [x/l for x in v]
def qangle(q,p):
    return math.degrees(2*math.acos(min(1.,abs(sum(x*y for x,y in zip(qnorm(q),qnorm(p)))))))
def qslerp(q,p,t):
    a,b=qnorm(q),qnorm(p); d=sum(x*y for x,y in zip(a,b))
    if d<0: b=[-x for x in b]; d=-d
    d=min(1.,d)
    if d>.9995: v=[x+(y-x)*t for x,y in zip(a,b)]
    else:
        angle=math.acos(d); v=[(math.sin((1-t)*angle)*x+math.sin(t*angle)*y)/math.sin(angle) for x,y in zip(a,b)]
    return unreal.Quat(*v).normalized()

def check_pose():
    agent.call_method('ApplyNNPoseKinematically',args=(0.,))
    values=levels()
    for n in names:
        t=values[0 if n.endswith('_l') else 1]; a,b=opens[n],closes[n]
        expected_pos=[x+(y-x)*t for x,y in zip(xyz(a.translation),xyz(b.translation))]
        expected_scale=[x+(y-x)*t for x,y in zip(xyz(a.scale3d),xyz(b.scale3d))]
        expected_q=qslerp(a.rotation,b.rotation,t)
        child=mesh.get_socket_transform(n,unreal.RelativeTransformSpace.RTS_COMPONENT)
        parent=mesh.get_socket_transform(parents[n],unreal.RelativeTransformSpace.RTS_COMPONENT)
        pos=parent.inverse_transform_location(child.translation)
        scale=[x/y for x,y in zip(xyz(child.scale3d),xyz(parent.scale3d))]
        rot=parent.rotation.inversed()*child.rotation
        pe=math.dist(xyz(pos),expected_pos); qe=qangle(rot,expected_q); se=math.dist(scale,expected_scale)
        state['max_position_cm']=max(state['max_position_cm'],pe)
        state['max_angle_deg']=max(state['max_angle_deg'],qe)
        state['max_scale']=max(state['max_scale'],se)
        assert pe<.01 and qe<.05 and se<.001,(n,pe,qe,se,values)

def begin(name,s,half=True,freeze=True):
    prior=levels()
    assert agent.call_method('SetAttackFistSettings',args=(unreal.Name(name),s))
    agent.set_editor_property('nn_inference_enabled',True)
    target=mesh.get_socket_location('pelvis')+unreal.Vector(0,110,10)
    assert agent.call_method('TriggerNNAttack',args=(unreal.Name(name),target,half))
    if freeze: agent.set_editor_property('nn_inference_enabled',False)
    state.update(start=now(),**{'from':prior,'target':[s.get_editor_property('LeftClosedLevel'),s.get_editor_property('RightClosedLevel')],'duration':s.get_editor_property('ClosingStartSeconds')})
    if state['duration']>0: assert math.dist(prior,levels())<1e-5,'Trigger snapped'

def stop():
    prior=levels()
    assert agent.call_method('StopNNAttack')
    state.update(start=now(),**{'from':prior,'target':[0.,0.]})
    if state['duration']>0: assert math.dist(prior,levels())<1e-5,'Stop snapped'

def finish(error=None):
    if state['handle'] is not None:
        unreal.unregister_slate_post_tick_callback(state['handle']); state['handle']=None
    report={k:v for k,v in state.items() if k!='handle'}
    report.update(passed=error is None,error=error,actor=agent.get_path_name(),mesh=mesh.get_skeletal_mesh_asset().get_path_name())
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2))
    unreal.log('Attack fist audit '+str(output)+' error='+str(error))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()

def tick(delta):
    try:
        phase=state['phase']; elapsed=now()-state['start']
        if phase==-1:
            assert levels()==[0.,0.]
            check_pose(); begin('jabR',settings(1.,.35)); state['phase']=0; return
        if phase<=3:
            alpha=1. if state['duration']<=0 else min(1.,max(0.,elapsed/state['duration']))
            expected=[a+(b-a)*alpha for a,b in zip(state['from'],state['target'])]
            le=math.dist(levels(),expected); state['max_level_error']=max(state['max_level_error'],le)
            assert le<1e-5,(phase,elapsed,levels(),expected)
            check_pose()
            state['rows'].append({'phase':phase,'elapsed':elapsed,'levels':levels()})
        if phase==0 and elapsed>=.6:
            state['duration']=1.; stop(); state['phase']=1
        elif phase==1 and elapsed>=.35:
            begin('hookL',settings(.2,1.,.2,.3),False); state['phase']=2
        elif phase==2 and elapsed>=.4:
            state['duration']=.3; stop(); state['phase']=3
        elif phase==3 and elapsed>=.5:
            assert levels()==[0.,0.]
            begin('jabL',settings(.6,.8,0.,0.)); check_pose()
            prior=levels()
            assert not agent.call_method('TriggerNNAttack',args=(unreal.Name('NOT_AN_ATTACK'),unreal.Vector(0,100,100),False))
            assert levels()==prior
            state['duration']=0.; stop(); assert levels()==[0.,0.]; check_pose()
            # Native physical modes preserve the animated local finger transforms.
            begin('jabR',settings(1.,1.,0.,.1)); state['phase']=4; state['start']=now()
        elif phase in (4,5,6) and elapsed>=.3:
            check_pose()
            modes={4:'HalfSim',5:'Physical',6:'Kinematic'}
            unreal.SystemLibrary.execute_console_command(world,'ke '+agent.get_path_name()+' SetSimulationMode '+modes[phase])
            state['phase']+=1; state['start']=now()
        elif phase==7 and elapsed>=.3:
            check_pose(); state['duration']=.1; stop()
            # Automatic policy completion, not just explicit Stop.
            begin('jabR',settings(),True,False); state['phase']=8; state['start']=now()
        elif phase==8:
            if not agent.call_method('GetNNAttackState'):
                state['phase']=9; state['start']=now()
            elif elapsed>12: raise RuntimeError('Natural attack did not finish within 12 game seconds')
        elif phase==9 and elapsed>=1.1:
            assert levels()==[0.,0.],levels()
            check_pose()
            assert agent.set_fist_closed_levels(.25,.8,.3)
            state['phase']=10; state['start']=now()
        elif phase==10:
            alpha=min(1.,elapsed/.3)
            assert math.dist(levels(),[.25*alpha,.8*alpha])<1e-5
            check_pose()
            if elapsed>=.8:
                assert math.dist(levels(),[.25,.8])<1e-6
                begin('hookR',settings(1.,.1,.2,.25)); state['phase']=11
        elif phase==11 and elapsed>=.4:
            check_pose()
            assert agent.call_method('StopNNAttack')
            state['phase']=12; state['start']=now()
        elif phase==12 and elapsed>=.5:
            assert math.dist(levels(),[.25,.8])<1e-6,'Attack did not return to manual levels'
            check_pose()
            begin('jabL',settings(1,1,.4,.4))
            assert agent.set_fist_closed_levels(.7,.3,.2)
            state['phase']=13; state['start']=now()
        elif phase==13 and elapsed>=.4:
            assert math.dist(levels(),[.7,.3])<1e-6
            check_pose(); assert agent.call_method('StopNNAttack')
            state['phase']=14; state['start']=now()
        elif phase==14 and elapsed>=.6:
            assert math.dist(levels(),[.7,.3])<1e-6,'Stop overrode manual takeover'
            assert agent.set_fist_closed_levels(0,0,.3)
            state['phase']=15; state['start']=now()
        elif phase==15:
            # Repeated identical calls must not restart or stall the blend.
            assert agent.set_fist_closed_levels(0,0,.3)
            if elapsed>=.5:
                assert levels()==[0.,0.]
                check_pose()
                unreal.SystemLibrary.execute_console_command(world,'ke '+agent.get_path_name()+' SetSimulationMode Physical')
                assert agent.set_fist_closed_levels(.4,1,.3)
                state['phase']=16; state['start']=now()
        elif phase==16 and elapsed>=.7:
            assert math.dist(levels(),[.4,1])<1e-6
            check_pose(); finish()
    except Exception:
        finish(traceback.format_exc())

state['handle']=unreal.register_slate_post_tick_callback(tick)
print('Attack fist audit running on '+agent.get_path_name())
