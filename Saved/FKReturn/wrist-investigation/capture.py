import unreal,json,time,traceback
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
out=Path(unreal.Paths.project_dir()).resolve()/'Saved/FKReturn/wrist-investigation'
s={'start':time.monotonic(),'last':None,'ticks':0,'seen':False,'tail':0,'rows':[],'owned':True}
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['callback'])
    w=ed.get_game_world()
    if w:unreal.SystemLibrary.execute_console_command(w,'Prophecy.FKReturn.Audit 0')
    (out/'capture.json').write_text(json.dumps({'error':error,'ticks':s['ticks'],'seen':s['seen'],'rows':s['rows']}))
    print('WRIST_CAPTURE_DONE',error or 'complete')
    if w and s['owned']:level.editor_request_end_play()
def tr(t):return [t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w,t.translation.x,t.translation.y,t.translation.z]
def tick(_):
    try:
        if time.monotonic()-s['start']>45:finish('timeout');return
        w=ed.get_game_world()
        if not w:return
        now=unreal.GameplayStatics.get_time_seconds(w)
        if now==s['last']:return
        s['last']=now;s['ticks']+=1
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        if s['ticks']==2:unreal.SystemLibrary.execute_console_command(w,'Prophecy.FKReturn.Audit 1')
        state=a.get_nn_attack_state()
        attack=str(state[0]) if state else ''
        if attack=='slashLU':s['seen']=True
        if s['seen'] and attack!='slashLU':s['tail']+=1
        names,future,presented,alpha=a.read_nn_future_world_pose()
        if len(names)==25:
            s['rows'].append({'tick':s['ticks'],'time':now,'attack':attack,'frame':int(state[4]) if state else -1,
              'names':[str(n) for n in names],'future':[tr(t) for t in future],
              'presented':[tr(t) for t in presented],'alpha':alpha,'mode':str(a.get_simulation_mode())})
        if s['tail']>=35:finish()
        elif s['ticks']>=1000:finish('No completed slashLU captured')
    except Exception:finish(traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
