"""Owned short TestNN play check. Logs the normal scene attack handoffs, then exits PIE."""
import unreal,time,json,traceback
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
out=Path(unreal.Paths.project_saved_dir())/'FKReturn/feedback-fix/smoke.json'
s={'start':time.monotonic(),'last':None,'ticks':0,'agents':0,'pose_samples':0,'saw_attack':False,'ended':False,'settings':False,'rows':[]}
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['callback'])
    w=ed.get_game_world()
    if w:
        unreal.SystemLibrary.execute_console_command(w,'Prophecy.FKReturn.Audit 0')
        unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 0')
    report={k:v for k,v in s.items() if k not in ('callback','start')};report['error']=error
    out.write_text(json.dumps(report,indent=2));print('FK_RETURN_SMOKE_DONE',error or 'complete')
    if w:level.editor_request_end_play()
def tick(_):
    try:
        if time.monotonic()-s['start']>70:finish('timeout');return
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['ticks']+=1
        agents=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
        if not agents:return
        if not s['settings']:
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.FKReturn.Audit 1')
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 220')
            s['agents']=len(agents);s['settings']=True
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        state=a.get_nn_attack_state()
        if state:s['saw_attack']=True
        elif s['saw_attack']:s['ended']=True
        if s['ticks']>=95 and s['ticks']%10==0:
            names,future,presented,alpha=a.read_nn_future_world_pose()
            assert len(names)>=16 and len(future)==len(names) and len(presented)==len(names)
            for tr in presented:
                values=[tr.translation.x,tr.translation.y,tr.translation.z,tr.rotation.x,tr.rotation.y,tr.rotation.z,tr.rotation.w]
                assert all(abs(x)<1e8 for x in values),values
            s['pose_samples']+=1
            s['rows'].append({'time':t,'state':str(state),'bones':len(names),'alpha':alpha})
        if s['ended'] and s['ticks']>=260:finish()
        elif s['ticks']>=480:finish('No completed attack observed' if not s['ended'] else '')
    except Exception:finish(traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
