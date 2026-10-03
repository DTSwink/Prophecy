import unreal, time, json
from pathlib import Path

editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world(), 'Start with PIE stopped'
library=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJointDampingLibrary'))
agent_class=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAgent')
state=dict(start=time.monotonic(),frames=0,configured=False)
path=Path(unreal.Paths.project_saved_dir())/'Diagnostics/JointDampingPolicyPIE.json'

def check(delta):
    world=editor.get_game_world()
    try:
        if world:
            state['frames']+=1
            if not state['configured'] and state['frames']>10:
                agents=unreal.GameplayStatics.get_all_actors_of_class(world,agent_class)
                for agent in agents:
                    if agent.is_jolt_physical_animation_enabled():
                        value=library.call_method('SetJoltJointLocomotionDamping',(agent,'lowerarm_r',10.,30.,100.,300.))
                        state['result']=str(value)
                        assert value is not None, 'Profile setter rejected request'
                        state['configured']=True
                        state['agent']=agent.get_name()
                        state['configured_frame']=state['frames']
                        break
        finished=state['configured'] and state['frames']>=state['configured_frame']+60
        if not finished and time.monotonic()-state['start']<45: return
        state['success']=bool(finished)
    except Exception as error:
        state['success']=False
        state['error']=str(error)
    unreal.unregister_slate_post_tick_callback(state.pop('callback'))
    if world: level.editor_request_end_play()
    path.write_text(json.dumps(state,indent=2))
    print('Damping policy short PIE check: '+json.dumps(state))

unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'Automation RunTests Prophecy.Jolt.Joints.DampingPolicy')
state['callback']=unreal.register_slate_post_tick_callback(check)
level.editor_request_begin_play()
print('Requested one policy test and short PIE profile check')
