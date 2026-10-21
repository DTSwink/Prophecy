"""Own one current-map Play; record the first pike admission without changing tuning."""
import json, pathlib, time, traceback, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'User Play left untouched'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CleanPike'
probe={'world':None,'handle':None,'start':time.monotonic(),'samples':[],'first_cut':None,'last_time':None}
physics=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJoltStandardPhysicsLibrary'))
log=pathlib.Path(unreal.Paths.project_log_dir())/'GameAnimationSample3.log'
probe['offset']=log.stat().st_size
def vector(v):return [v.x,v.y,v.z]
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(probe['handle'])
    if probe['world'] and ed.get_game_world()==probe['world']:le.editor_request_end_play()
    (out/'play.json').write_text(json.dumps({'error':error,'first_cut':probe['first_cut'],'samples':probe['samples']},indent=2))
    with log.open('rb') as f:f.seek(probe['offset']);text=f.read().decode('utf-8',errors='replace')
    (out/'play-log.txt').write_text(text)
def tick(dt):
    try:
        w=ed.get_game_world()
        if not w:
            if probe['world'] or time.monotonic()-probe['start']>30:finish('Play ended or startup timeout')
            return
        if not probe['world']:probe['world']=w;probe['play_start']=time.monotonic()
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==probe['last_time']:return
        probe['last_time']=t
        for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
            if not a.get_class().get_name().startswith('A_Sword_C'):continue
            c=next((c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.get_name().lower()=='sword'),None)
            if not c:continue
            row={'t':t,'name':a.get_name(),'pike':bool(a.get_editor_property('temp pike')),
                 'cuts':len(a.get_editor_property('cuts')),'position':vector(c.get_world_location()),
                 'incoming_velocity':vector(a.get_editor_property('current vel')),
                 'velocity':vector(physics.call_method('GetPhysicsLinearVelocity',(c,unreal.Name('None'))))}
            probe['samples'].append(row)
            if row['cuts'] and row['pike'] and not probe['first_cut']:
                probe['first_cut']=row;probe['cut_time']=time.monotonic()
        if probe['first_cut'] and time.monotonic()-probe['cut_time']>1:finish()
        elif time.monotonic()-probe['play_start']>20:finish('No accepted pike within 20 wall seconds')
    except Exception:finish(traceback.format_exc())
probe['handle']=unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play()
print('Owned current-map clean-pike probe started')
