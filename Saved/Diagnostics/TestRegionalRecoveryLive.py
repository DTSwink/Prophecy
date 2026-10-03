import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RegionalRecovery';out.mkdir(exist_ok=True)
log=pathlib.Path(unreal.Paths.project_saved_dir())/'Logs/GameAnimationSample3.log'
s=dict(start=time.monotonic(),a=None,case=-1,action=-1,rows=[],events=[],offset=log.stat().st_size)
cases=[('half',[True]),('full',[False]),('full_half',[False,True]),('half_full',[True,False]),('full_half_full_half',[False,True,False,True])]
bones=['pelvis','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r']
def xyz(v):return [v.x,v.y,v.z]
def pose(a):
    names,future,presented,alpha=a.read_nn_future_world_pose()
    return {str(n):dict(future=xyz(f.translation),presented=xyz(p.translation)) for n,f,p in zip(names,future,presented) if str(n) in bones}
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    w=ed.get_game_world()
    if w:unreal.SystemLibrary.execute_console_command(w,'Prophecy.Recovery.RegionAudit 0')
    with log.open('rb') as f:f.seek(s['offset']);(out/'live.log').write_bytes(f.read())
    (out/'live.json').write_text(json.dumps(dict(error=error,rows=s['rows'],events=s['events']),indent=2))
    if w:level.editor_request_end_play()
    print('REGIONAL_RECOVERY_LIVE_DONE',error or 'passed')
def tick(_):
    try:
        assert time.monotonic()-s['start']<150,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t<.65:return
        if not s['a']:
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
                a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
                a.set_actor_tick_enabled(False);a.stop_nn_attack()
                a.stop_locomotion_input()
            s['a']=unreal.GameplayStatics.get_player_pawn(w,0)
            assert int(s['a'].get_editor_property('codex slash train index'))==0,'Automatic attack train is active'
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.Recovery.RegionAudit 1')
        a=s['a'];case=int((t-1.2)/1.4) if t>=1.2 else -1
        if case>=len(cases):finish();return
        if case<0:return
        name,modes=cases[case]
        if case!=s['case']:
            assert not a.get_nn_attack_state(),'Prior case still active'
            s.update(case=case,action=0)
            p=a.get_authored_body_world_target('pelvis')[1].translation
            print('REGION_CASE',name,'BEGIN')
            assert a.trigger_nn_attack('slashR',p+unreal.Vector(-30,90,30),modes[0])
            s['events'].append(dict(case=name,action='trigger',half=modes[0]))
            s['until']=t+.07
        if t>=s['until'] and s['action']<len(modes):
            i=s['action']+1
            if i<len(modes):
                before=a.get_nn_attack_state();assert before,'Attack ended before switch'
                assert a.set_nn_half_attack_enabled(modes[i])
                after=a.get_nn_attack_state();assert before[2:]==after[2:]
                # Repeated same-mode calls must not emit additional end events.
                assert a.set_nn_half_attack_enabled(modes[i])
                s['events'].append(dict(case=name,action='switch',half=modes[i],frame=after[-1]))
            else:
                before=pose(a);root=a.get_root_low_point()
                assert a.stop_nn_attack()
                after=pose(a);root_after=a.get_root_low_point()
                if name=='half':
                    assert (root_after-root).length()<.00001,'Pure half moved the root at exit'
                    for b in bones:
                        assert sum((x-y)**2 for x,y in zip(before[b]['future'],after[b]['future']))<1.e-8,'Pure half changed lower pose at exit'
                s['events'].append(dict(case=name,action='stop',root_before=xyz(root),root_after=xyz(root_after),before=before,after=after))
                assert not a.stop_nn_attack(),'Repeated stop should be inactive'
                print('REGION_CASE',name,'STOPPED')
            s['action']=i;s['until']=t+.07
        s['rows'].append(dict(t=t,case=name,attack=str(a.get_nn_attack_state()),root=xyz(a.get_root_low_point()),pose=pose(a)))
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
