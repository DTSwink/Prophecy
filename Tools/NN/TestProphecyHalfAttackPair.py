"""Actual idle vs walking/running half attacks with identical upper-pose initialization.
The opt-in fixture copies upper pose only; each actor keeps its own real lower NN.
"""
import unreal,json,pathlib,time,traceback,builtins
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
s={'events':[],'rows':[],'last':-1,'phase':-1,'actors':[],'wall':time.perf_counter(),'case':-1,'turned':False}
builtins._half_pair=s
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts'
def v(p):return [p.x,p.y,p.z]
def tr(t):return {'p':v(t.translation),'q':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]}
def pelvis(a):
    names,future,_,_=a.read_nn_future_world_pose()
    return future[[str(n) for n in names].index('pelvis')]
def target(a):return pelvis(a).translation+unreal.Vector(-30,50,35)
def end(reason):
    unreal.unregister_slate_post_tick_callback(s['handle'])
    w=editor.get_game_world()
    if w:
        for cmd in ['Prophecy.SlashTraceFrames 0','Prophecy.SlashTraceAgent -1','Prophecy.SlashTestHalfUpperSource -1','Prophecy.SlashTestHalfRelativeTarget 0']:unreal.SystemLibrary.execute_console_command(w,cmd)
    (out/'HalfPair.json').write_text(json.dumps({'reason':reason,'events':s['events'],'rows':s['rows']}))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('HALF_PAIR_DONE',reason,len(s['rows']))
def tick(dt):
    try:
        w=editor.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        if not s['actors']:
            actors=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
            for a in actors:
                a.set_actor_tick_enabled(False);a.stop_nn_attack();a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            s['actors']=[next(a for a in actors if a.get_agent_handle().index==i) for i in [0,2]]
            for m in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyNNLocomotionManager):
                m.set_editor_property('clamp_foot',False);m.set_editor_property('clamp_calf',False)
            for i,a in enumerate(s['actors']):
                a.set_locomotion_input(unreal.Vector(0,i,0),False,unreal.Vector(i,1-i,0),1,1)
            for cmd in ['Prophecy.SlashTestHalfUpperSource 0','Prophecy.SlashTestHalfRelativeTarget 1','Prophecy.SlashTraceAgent -2','Prophecy.SlashTraceFrames 1600']:unreal.SystemLibrary.execute_console_command(w,cmd)
            s['events'].append({'t':t,'actors':[a.get_name() for a in s['actors']],'action':'idle/walk; BP tick disabled; independent lower policies'})
        if 19.0<t<19.1:
            s['actors'][1].set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(0,1,0),1,1)
        case=int((t-4)//8)
        if 0<=case<3 and case!=s['case']:
            s['case']=case;family=['hookL','headbutt','slashL'][case]
            moving=s['actors'][1];moving.set_locomotion_input(unreal.Vector(0,1,0),case>0,unreal.Vector(0,1,0),1,1)
            for a in s['actors']:a.stop_nn_attack()
            for a in s['actors']:assert a.trigger_nn_attack(family,target(a),True)
            s['events'].append({'t':t,'case':case,'family':family,'action':'match current upper pose only, then trigger both halves'})
        if t>=12.3 and not s['turned']:
            s['turned']=True
            s['actors'][1].set_locomotion_input(unreal.Vector(1,0,0),True,unreal.Vector(1,0,0),1,1)
            s['events'].append({'t':t,'action':'runner turns 90 degrees during Headbutt; upper attack must stay independent'})
        for a in s['actors']:
            attack=a.get_nn_attack_state()
            if attack:a.set_nn_attack_target(target(a))
            names,future,shown,alpha=a.read_nn_future_world_pose()
            s['rows'].append({'t':t,'case':s['case'],'actor':a.get_name(),'root':v(a.get_root_low_point()),'attack':str(attack[0]) if attack else None,'frame':attack[-1] if attack else 0,'armed':attack[2] if attack else False,'hit':attack[3] if attack else False,'future':{str(n):tr(f) for n,f in zip(names,future)}})
        if t>=28:end('Complete')
        elif time.perf_counter()-s['wall']>150:end('Timeout')
    except Exception:end(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('HALF_PAIR_STARTED')
