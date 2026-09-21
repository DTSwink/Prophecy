import unreal,json,pathlib,time,traceback,collections
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'User PIE running; leave untouched.'
s={'start':time.monotonic(),'agents':[],'bindings':[],'delegates':[],'events':[],'states':[],'phase':'original','original':{}}
def path(o):return o.get_path_name() if o else None
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    for delegate,fn in s['bindings']:
        try:delegate.remove_callable(fn)
        except:pass
    level.editor_request_end_play()
    out={k:s[k] for k in ['events','states','original']};out['error']=error
    p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PhysicalMeshHits/PIE.json'
    p.write_text(json.dumps(out,indent=2))
    print('PHYSICAL_MESH_HITS',len(s['events']),error)
def tick(dt):
    try:
        if time.monotonic()-s['start']>90:raise RuntimeError('timeout')
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if not s['agents']:
            agents=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            if not agents or not all(a.has_valid_agent_handle() for a in agents):return
            s['agents']=agents
            for a in agents:
                s['original'][a.get_name()]=bool(a.get_editor_property('generate_physical_hit_events'))
                for m in a.get_components_by_class(unreal.SkeletalMeshComponent):
                    if m.get_name()!='PhysicalMesh':continue
                    def on_hit(mine,other,component,impulse,hit):
                        s['events'].append(dict(t=unreal.GameplayStatics.get_time_seconds(w),phase=s['phase'],mine=path(mine),other=path(other),component=path(component),impulse=[impulse.x,impulse.y,impulse.z]))
                    d=m.on_component_hit;d.add_callable(on_hit);s['delegates'].append(d);s['bindings'].append((d,on_hit))
        if t>=3 and s['phase']=='original':
            s['phase']='enabled'
            for a in s['agents']:a.set_generate_physical_hit_events(True)
        if not s['states'] or t-s['states'][-1]['t']>=.25:
            rows=[]
            for a in s['agents']:
                rows.append(dict(name=a.get_name(),mode=str(a.get_simulation_mode()),jolt=a.is_jolt_physical_animation_enabled(),notify=bool(a.get_editor_property('generate_physical_hit_events')),state=str(unreal.ProphecyNNDefenseLibrary.get_agent_state(a))))
            s['states'].append(dict(t=t,phase=s['phase'],agents=rows))
        if t>=8:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()

