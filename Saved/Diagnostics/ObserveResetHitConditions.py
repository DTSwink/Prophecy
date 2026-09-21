import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user PIE'
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
s={'start':time.monotonic(),'frame':0,'actors':[],'states':[],'samples':[]}
def cmd(w,x):unreal.SystemLibrary.execute_console_command(w,x)
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    w=ed.get_game_world()
    if w:
        cmd(w,'Prophecy.Reset.HitAudit sample')
        cmd(w,'Prophecy.Reset.HitAudit stop')
        level.editor_request_end_play()
    (root/'ResetHitConditions.json').write_text(json.dumps({'error':error,'states':s['states'],'samples':s['samples']},indent=2))
    print('RESET_HIT_CONDITIONS',error or 'complete')
def tick(_):
    try:
        assert time.monotonic()-s['start']<70,'Timeout'
        w=ed.get_game_world()
        if not w:return
        s['frame']+=1
        if not s['actors']:
            s['actors']=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            cmd(w,'Prophecy.Reset.HitAudit start')
        for a in s['actors']:
            state=a.get_nn_attack_state()
            s['states'].append({'frame':s['frame'],'time':unreal.GameplayStatics.get_time_seconds(w),'agent':a.get_name(),'attack':str(state),'mode':str(unreal.ProphecyNNDefenseLibrary.get_agent_state(a))})
        if s['frame']==100:
            result=unreal.ProphecyAgentResetLibrary.reset_initial_agents(w)
            s['samples'].append({'frame':100,'reset_result':str(result)})
        if s['frame'] in (90,130,200,360):
            cmd(w,'Prophecy.Reset.HitAudit sample')
            s['samples'].append({'frame':s['frame'],'audit':json.loads((root/'ResetHitAudit.json').read_text(encoding='utf-8-sig'))})
        if s['frame']==200:
            a=unreal.GameplayStatics.get_player_pawn(w,0)
            others=[p for p in s['actors'] if p!=a]
            victim=min(others,key=lambda p:p.get_distance_to(a))
            for p in s['actors']:
                unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',(p,'bool debug 1',False))
                p.stop_nn_attack();p.stop_locomotion_input()
            target=next(c for c in victim.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='PhysicalMesh').get_socket_location('head')
            assert a.trigger_nn_attack('hookL',target,False,victim),'Post-reset attack rejected'
        if s['frame']>=360:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
cmd(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
level.editor_request_begin_play()
print('Observing hit predicates across explicit frame100 reset, then replaying a hook at the nearest opponent head.')
