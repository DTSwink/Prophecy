import unreal, builtins, pathlib, json, time, traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
s=dict(rows=[],actors=[],last=-1,wall=time.perf_counter(),phase=0)
builtins._handoff_survey=s
def tr(x):
    p=x.translation;q=x.rotation
    return [p.x,p.y,p.z,q.x,q.y,q.z,q.w]
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/HandoffControlledBefore.json'
    p.write_text(json.dumps(dict(reason=reason,rows=s['rows'])),encoding='utf-8')
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('HANDOFF_SURVEY',reason,len(s['rows']))
def tick(dt):
    try:
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        if not s['actors']:
            s['actors']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
            for a in s['actors']:
                a.set_actor_tick_enabled(False)
                a.stop_nn_attack()
                a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
                a.set_attack_foot_clamp(False,0);a.set_attack_calf_clamp(False,0)
            for m in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyNNLocomotionManager):
                for name in ['clamp_foot','clamp_calf','clamp_hand']:m.set_editor_property(name,False)
        # Observe the user's real graph first, then stop its chain explicitly.
        if t>=1 and s['phase']==0:
            for i,a in enumerate(s['actors']):
                a.trigger_nn_attack('hookR',a.get_root_low_point()+unreal.Vector(-30,50,115),bool(i%2))
            s['phase']=1
        if t>=2 and s['phase']==1:
            for a in s['actors']:
                a.set_actor_tick_enabled(False)
                a.stop_nn_attack()
            s['phase']=2
        for a in s['actors']:
            pose=a.read_nn_future_world_pose()
            if not pose:continue
            names,future,shown,alpha=pose
            ids={str(n):i for i,n in enumerate(names)}
            attack=a.get_nn_attack_state()
            s['rows'].append(dict(t=t,actor=a.get_name(),attack=str(attack),phase=s['phase'],root=tr(a.get_actor_transform()),future={b:tr(future[ids[b]]) for b in ['pelvis','hand_l','hand_r','foot_l','foot_r','upperarm_r','lowerarm_r']},shown={b:tr(shown[ids[b]]) for b in ['pelvis','hand_l','hand_r','foot_l','foot_r']}))
        if t>=4:finish('Complete')
        elif time.perf_counter()-s['wall']>120:finish('Timeout')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
