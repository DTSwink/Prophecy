import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'User PIE running; leave untouched.'
s={'start':time.monotonic(),'agents':[],'rows':[],'events':[],'bindings':[],'editor':[],'starts':[],'next':1.0}
for a in unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),unreal.ProphecyAgent):
    if a.get_editor_property('CombatDemoEnabled'):
        s['editor'].append((a,a.get_actor_location()))
        if a.get_editor_property('auto_possess_player')==unreal.AutoReceiveInput.PLAYER0:
            p=a.get_actor_location();p.x=0;a.set_actor_location(p,False,True)
def restore():
    for a,p in s['editor']:a.set_actor_location(p,False,True)
    s['editor']=[]
def v(x):return [x.x,x.y,x.z]
def finish(err=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    for d,f in s['bindings']:
        try:d.remove_callable(f)
        except:pass
    level.editor_request_end_play();restore()
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/HooksAttacks.json').write_text(json.dumps(dict(rows=s['rows'],events=s['events'],starts=s['starts'],error=err)))
    print('HOOKS',len(s['rows']),len(s['events']),err)
def tick(dt):
    try:
        if time.monotonic()-s['start']>100:raise RuntimeError('timeout')
        w=ed.get_game_world()
        if not w:return
        if not s['agents']:
            agents=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            if not agents or not all(a.has_valid_agent_handle() for a in agents):return
            restore()
            s['agents']=[a for a in agents if a.get_editor_property('CombatDemoEnabled')]
            for a in s['agents']:
                a.set_generate_physical_hit_events(True)
                m=next(m for m in a.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name()=='PhysicalMesh')
                def hit(mine,other,component,impulse,result):
                    s['events'].append(dict(t=unreal.GameplayStatics.get_time_seconds(w),mine=mine.get_owner().get_name(),other=other.get_name() if other else '',component=component.get_name() if component else '',impulse=v(impulse)))
                d=m.on_component_hit;d.add_callable(hit);s['bindings'].append((d,hit))
        t=unreal.GameplayStatics.get_time_seconds(w);rows=[]
        attacker=unreal.GameplayStatics.get_player_pawn(w,0);victim=next(a for a in s['agents'] if a!=attacker)
        target=victim.get_physical_body_state('head')[0].translation
        if t>=s['next']:
            family='hookl' if len(s['starts'])%2==0 else 'hookr'
            ok=attacker.trigger_nn_attack(family,target,False,victim)
            defense=unreal.ProphecyNNDefenseLibrary.start_nn_dodge(victim,attacker) if ok else 'attack failed'
            s['starts'].append(dict(t=t,family=family,ok=ok,defense=defense));s['next']+=2
        attacker.set_nn_attack_target(target)
        for a in s['agents']:
            d=dict(name=a.get_name(),tick=a.get_editor_property('tick debug'),root=v(a.get_actor_location()),state=str(unreal.ProphecyNNDefenseLibrary.get_agent_state(a)),attack=str(a.get_nn_attack_state()),bones={})
            for bone in ['head','hand_l','hand_r']:
                b=a.get_physical_body_state(bone)
                if b:d['bones'][bone]={'p':v(b[0].translation),'v':v(b[1]),'sim':b[3]}
            rows.append(d)
        s['rows'].append(dict(t=t,agents=rows))
        if t>=10:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
