import unreal,json,pathlib,time
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
s={'start':time.monotonic(),'rows':[],'last':None,'next':0}
def tick(_):
    w=ed.get_game_world()
    if not w:return
    t=unreal.GameplayStatics.get_time_seconds(w)
    agents=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
    setups=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyJoltFightSetup)
    state={'agents':[{'name':a.get_name(),'mode':str(a.get_simulation_mode()),'enabled':a.is_jolt_physical_animation_enabled(),'selected':a.is_jolt_physical_animation_selected()} for a in agents],'setup':[{'started':a.get_editor_property('started_agent_count'),'error':a.get_editor_property('last_error')} for a in setups]}
    if state!=s['last'] or t>=s['next']:
        s['rows'].append({'time':t,**state});s['last']=state;s['next']=t+1
    if t>=6 or time.monotonic()-s['start']>35:
        unreal.unregister_slate_post_tick_callback(s['cb'])
        (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CurrentBackendTrace.json').write_text(json.dumps(s['rows'],indent=2))
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
