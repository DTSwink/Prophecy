import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user PIE'
s={'start':time.monotonic(),'frame':0,'checks':[]}
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if ed.get_game_world():level.editor_request_end_play()
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/ResetSword.json').write_text(json.dumps({'error':error,'checks':s['checks']},indent=2))
    print('RESET_SWORD',error or 'passed')
def tick(_):
    try:
        assert time.monotonic()-s['start']<75,'Timeout'
        w=ed.get_game_world()
        if not w:return
        s['frame']+=1
        f=s['frame']
        if f==15:
            agents=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            for a in agents:
                unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',(a,'bool debug 1',False))
                unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',(a,'dead debug',True))
                a.stop_nn_attack();a.stop_locomotion_input()
            a=unreal.GameplayStatics.get_player_pawn(w,0)
            sword=a.get_held_sword()
            assert sword,'Starting sword missing'
            s.update(agent=a,mode=a.is_sword_simulated(),cls=sword.get_class(),count=len(unreal.GameplayStatics.get_all_actors_of_class(w,sword.get_class())))
            assert unreal.ProphecyAgentResetLibrary.initialize_agent_reset(w) is not None,'Capture failed'
        if f in (20,55):
            a=s['agent'];s['old']=a.get_held_sword()
            assert a.drop_sword(),'Drop rejected'
        if f in (28,63):
            assert not s['agent'].get_held_sword(),'Drop did not complete'
            assert unreal.ProphecyAgentResetLibrary.reset_initial_agents(w) is not None,'Reset rejected'
        if f in (45,80,110):
            a=s['agent'];new=a.get_held_sword()
            assert new,'Reset did not restore held sword'
            assert a.is_sword_simulated()==s['mode'],'Held mode changed'
            assert not unreal.SystemLibrary.is_valid(s['old']),'Old sword remains in world'
            count=len(unreal.GameplayStatics.get_all_actors_of_class(w,s['cls']))
            assert count==s['count'],f'Duplicate swords: {count} vs {s["count"]}'
            s['checks'].append({'frame':f,'restored':new.get_name(),'simulated':a.is_sword_simulated(),'sword_count':count})
        if f==90:
            s['old']=s['agent'].get_held_sword();s['agent'].hide_sword()
            assert unreal.ProphecyAgentResetLibrary.reset_initial_agents(w) is not None,'Reset after destruction rejected'
        if f>=110:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('Checking two drop/reset cycles and destroyed-sword recovery; no asset changes.')
