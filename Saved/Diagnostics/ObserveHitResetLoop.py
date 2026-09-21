import unreal,json,pathlib,time,traceback,sys
clear_flag=len(sys.argv)>1 and sys.argv[1]=='clear-flag'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user PIE'
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
s={'start':time.monotonic(),'frame':0,'actors':[],'states':[]}
def cmd(w,x):unreal.SystemLibrary.execute_console_command(w,x)
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    w=ed.get_game_world()
    if w:
        cmd(w,'Prophecy.Reset.HitAudit sample')
        cmd(w,'Prophecy.Reset.HitAudit stop')
        level.editor_request_end_play()
    (root/('HitResetLoopClearFlag.json' if clear_flag else 'HitResetLoop.json')).write_text(json.dumps({'error':error,'states':s['states']},indent=2))
    print('HIT_RESET_LOOP',error or 'complete')
def tick(_):
    try:
        assert time.monotonic()-s['start']<90,'Timeout'
        w=ed.get_game_world()
        if not w:return
        s['frame']+=1
        if not s['actors']:
            s['actors']=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            cmd(w,'Prophecy.Reset.HitAudit start')
        if clear_flag and s['frame']==140:
            for a in s['actors']:
                unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',(a,'dead debug',False))
        for a in s['actors']:
            p=a.get_actor_location()
            row={'frame':s['frame'],'time':unreal.GameplayStatics.get_time_seconds(w),'agent':a.get_name(),'attack':str(a.get_nn_attack_state()),'pos':[p.x,p.y,p.z]}
            for name in ('dead debug','tick debug','bool debug 1','bool debug 2'):
                try:row[name]=str(a.get_editor_property(name))
                except Exception:pass
            s['states'].append(row)
        if s['frame']>=600:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
cmd(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
level.editor_request_begin_play()
print('Observing unchanged hit-delay-reset Blueprint loop for 600 frames.')
