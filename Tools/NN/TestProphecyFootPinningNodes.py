"""Transient correctness checks for pinning capture and per-agent threshold. No benchmarking."""
import builtins,json,pathlib,traceback,math,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
s=dict(actors={},phase=0,rows=[],forced=False,zero_checks=0,attack_checks=0,last=-1)
builtins._foot_pin_nodes=s
def vals(p):return [p.x,p.y]
def record(p):return dict(raw=vals(p.raw_network_output),decoded=vals(p.raw_pinning),effective=vals(p.effective_pinning),time=p.sample_time_seconds,visible=p.applies_to_visible_feet,walk=p.walk_policy)
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/BackwardTurn/PinningNodes.json').write_text(json.dumps(dict(reason=reason,forced=s['forced'],zero_checks=s['zero_checks'],attack_checks=s['attack_checks'],rows=s['rows'])))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('PINNING_NODES_CHECK',reason)
def tick(_):
    try:
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        if not s['actors']:
            s['actors']={a.get_agent_handle().index:a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)}
            assert 0 in s['actors'] and 2 in s['actors']
            for a in s['actors'].values():assert a.get_locomotion_foot_pinning() is None
            for i in [0,2]:assert s['actors'][i].set_foot_pinning_debug_enabled(True)
            assert not s['actors'][0].set_locomotion_foot_pinning_threshold(-1,.5)
            assert not s['actors'][0].set_locomotion_foot_pinning_threshold(2,-1)
        a=s['actors'][0]
        p=a.get_locomotion_foot_pinning()
        if p:
            r=record(p);r['t']=t;s['rows'].append(r)
            assert all(math.isfinite(v) for k in ['raw','decoded','effective'] for v in r[k])
            assert all(0<=v<=1 for k in ['decoded','effective'] for v in r[k])
            if 1.2<t<2 and any(e>d+.1 for e,d in zip(r['effective'],r['decoded'])):s['forced']=True
            if 2.25<t<2.7:
                assert r['effective']==r['decoded']
                s['zero_checks']+=1
        if t>=2.17 and s['phase']==0:
            assert a.set_locomotion_foot_pinning_threshold(0,.5)
            s['phase']=1
        if t>=2.8 and s['phase']==1:
            assert a.set_locomotion_foot_pinning_threshold(2,.5)
            for i in [0,2]:
                actor=s['actors'][i]
                actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
                actor.set_actor_tick_enabled(False)
                actor.stop_nn_attack()
                assert actor.trigger_nn_attack('hookR',actor.get_root_low_point()+unreal.Vector(-30,50,115),i==2)
            s['phase']=2
        if 2.9<t<3.2:
            for i in [0,2]:
                actor=s['actors'][i]
                p=actor.get_attack_foot_pinning(False)
                f=actor.get_attack_foot_pinning(True)
                assert p and f
                r=record(p);fr=record(f)
                assert r['decoded']==r['effective']
                assert r['visible']==(i==0) and not fr['visible']
                for raw,e in zip(r['raw'],r['effective']):assert abs(max(0,min(1,2/(1+math.exp(-raw))-1))-e)<1e-6
                l,rraw=fr['raw'];both=l<0 and rraw<0
                assert fr['effective']==[float(both or l<=rraw),float(both or rraw<l)]
                s['attack_checks']+=1
        if t>=3.3:
            assert s['forced'] and s['zero_checks']>5 and s['attack_checks']>5
            for i in [0,2]:
                actor=s['actors'][i]
                actor.stop_nn_attack()
                assert actor.get_attack_foot_pinning(False) is None
                assert actor.set_foot_pinning_debug_enabled(False)
                assert actor.get_locomotion_foot_pinning() is None
            finish('passed')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
