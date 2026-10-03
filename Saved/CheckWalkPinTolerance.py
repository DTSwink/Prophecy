import unreal,time,json
from pathlib import Path
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world(), 'Start with PIE stopped'
library=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary'))
agent_class=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAgent')
state=dict(start=time.monotonic(),frames=0,configured=False)
path=Path(unreal.Paths.project_saved_dir())/'Diagnostics/WalkPinTolerancePIE.json'
def check(delta):
    world=editor.get_game_world()
    try:
        if world:
            state['frames']+=1
            if not state['configured'] and state['frames']>10:
                agents=unreal.GameplayStatics.get_all_actors_of_class(world,agent_class)
                if agents:
                    agent=agents[0]
                    assert library.call_method('SetWalkPinningTolerance',(agent,.125,.5))
                    assert tuple(library.call_method('GetWalkPinningTolerance',(agent,)))==(.125,.5)
                    assert not library.call_method('SetWalkPinningTolerance',(agent,-1.,0.))
                    assert tuple(library.call_method('GetWalkPinningTolerance',(agent,)))==(.125,.5)
                    state['configured']=True
                    state['configured_frame']=state['frames']
        finished=state['configured'] and state['frames']>=state['configured_frame']+60
        if not finished and time.monotonic()-state['start']<45:return
        state['success']=bool(finished)
    except Exception as error:
        state['success']=False
        state['error']=str(error)
    unreal.unregister_slate_post_tick_callback(state.pop('callback'))
    if world:level.editor_request_end_play()
    path.write_text(json.dumps(state,indent=2))
    print('Walk pin tolerance check: '+json.dumps(state))
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'Automation RunTests Prophecy.NN.WalkPinning.Tolerance')
state['callback']=unreal.register_slate_post_tick_callback(check)
level.editor_request_begin_play()
print('Requested one walk-pinning unit test and short PIE setter check')
