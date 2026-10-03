"""Read-only sample of the current user PIE session; never starts/stops it."""
import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world(),'No current Play session'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyGhostAttackLibrary'))
s=dict(start=time.monotonic(),last=None,rows=[])
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/AttackControls/user-live-counter.json').write_text(json.dumps(dict(error=error,rows=s['rows']),indent=2))
    print('LIVE_ATTACK_COUNTER_INSPECTED',error or 'complete',len(s['rows']))
def tick(_):
    try:
        w=ed.get_game_world()
        if not w:finish('Play ended');return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t!=s['last']:
            s['last']=t
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
                if not a.is_player_controlled():continue
                s['rows'].append(dict(time=t,actor=a.get_path_name(),ticks=api.call_method('GetTicksSinceLastAttack',args=(a,)),attack=str(a.get_nn_attack_state())))
        if time.monotonic()-s['start']>4:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
