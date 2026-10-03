"""Owned 265-tick scene check: finite pin samples and unboosted pure Run weights."""
import json, math, pathlib, time, traceback, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None, 'Preserve user Play'
s=dict(world=None,actors=[],rows=[],ticks=0,last=None,start=time.monotonic(),run_checks=0,attack_seen=set())
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RemoveRunPinBoost20261003'
    out.mkdir(exist_ok=True)
    (out/'pin-readback.json').write_text(json.dumps(dict(reason=reason,run_checks=s['run_checks'],rows=s['rows'])))
    if s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
    print('PINNING_NODES_CHECK',reason,'Run checks',s['run_checks'])
def tick(_):
    try:
        if time.monotonic()-s['start']>60:finish('Watchdog');return
        w=ed.get_game_world()
        if w is None:
            if s['world'] is not None:finish('Play ended early')
            return
        if s['world'] is None:
            s['world']=w
            s['actors']=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            assert s['actors']
            for a in s['actors']:assert a.set_foot_pinning_debug_enabled(True)
        if w!=s['world']:finish('World replaced');return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['ticks']+=1
        for a in s['actors']:
            p=a.get_locomotion_foot_pinning()
            if p is None:continue
            decoded=[p.raw_pinning.x,p.raw_pinning.y]
            effective=[p.effective_pinning.x,p.effective_pinning.y]
            assert all(math.isfinite(v) and 0<=v<=1 for v in decoded+effective)
            if a.get_nn_attack_state():s['attack_seen'].add(a.get_name())
            weights=a.get_locomotion_checkpoint_weights()
            # Before the first attack, leg/pelvis mixtures agree. Later regional
            # recovery can include independent Walk leg controls; skip equality there.
            if p.applies_to_visible_feet and weights and weights[0]==0 and a.get_name() not in s['attack_seen']:
                assert decoded==effective,(a.get_name(),decoded,effective,weights)
                s['run_checks']+=1
                s['rows'].append(dict(tick=s['ticks'],actor=a.get_name(),decoded=decoded,effective=effective))
        if s['ticks']>=265:
            assert s['run_checks']>20,s['run_checks']
            finish('passed')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('PINNING_NODES_CHECK_STARTED')
