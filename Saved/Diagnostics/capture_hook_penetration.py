import unreal,json,pathlib,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Leave user PIE untouched.'
steps=int(sys.argv[1]) if len(sys.argv)>1 else 1
s={'start':time.monotonic(),'agents':[],'rows':[],'editor':[],'starts':[],'next':1.0,'steps':steps}
for a in unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),unreal.ProphecyAgent):
    if a.get_editor_property('CombatDemoEnabled'):
        s['editor'].append((a,a.get_actor_location()))
        if a.get_editor_property('auto_possess_player')==unreal.AutoReceiveInput.PLAYER0:
            p=a.get_actor_location();p.x=0;a.set_actor_location(p,False,True)
def restore():
    for a,p in s['editor']:a.set_actor_location(p,False,True)
    s['editor']=[]
def finish(err=''):
    unreal.unregister_slate_post_tick_callback(s['cb']);level.editor_request_end_play();restore()
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/HookPenetration_'+str(steps)+'.json').write_text(json.dumps(dict(rows=s['rows'],starts=s['starts'],steps=steps,error=err)))
    print('HOOK_PENETRATION_END',steps,len(s['rows']),err)
def tick(dt):
    try:
        if time.monotonic()-s['start']>150:raise RuntimeError('timeout')
        w=ed.get_game_world()
        if not w:return
        if not s['agents']:
            actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            if not actors or not all(a.has_valid_agent_handle() for a in actors):return
            restore();s['agents']=[a for a in actors if a.get_editor_property('CombatDemoEnabled')]
            lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJoltBlueprintLibrary'))
            assert lib.call_method('SetJoltCollisionSubsteps',(w,steps>1,steps))
            print('HOOK_PENETRATION_BEGIN',steps)
            for a in s['agents']:assert a.set_jolt_ccd_mode(unreal.ProphecyJoltCCDMode.DISCRETE)==''
        t=unreal.GameplayStatics.get_time_seconds(w)
        attacker=unreal.GameplayStatics.get_player_pawn(w,0);victim=next(a for a in s['agents'] if a!=attacker)
        target=victim.get_physical_body_state('head')[0].translation
        if t>=s['next']:
            family='hookl' if len(s['starts'])%2==0 else 'hookr'
            ok=attacker.trigger_nn_attack(family,target,False,victim)
            defense=unreal.ProphecyNNDefenseLibrary.start_nn_dodge(victim,attacker) if ok else 'failed'
            s['starts'].append(dict(t=t,family=family,ok=ok,defense=defense));s['next']+=2
        attacker.set_nn_attack_target(target)
        attack=attacker.get_nn_attack_state()
        if t>=1:
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.Debug.MeasureHandHead '+attacker.get_name()+' '+victim.get_name())
        s['rows'].append(dict(t=t,tick=attacker.get_editor_property('tick debug'),attack=str(attack),defense=str(unreal.ProphecyNNDefenseLibrary.get_agent_state(victim))))
        if t>=10:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
