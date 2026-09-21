import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
started_here=not bool(ed.get_game_world())
smooth=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNRootWindowLibrary'))
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
s={'rows':[],'start':time.monotonic(),'first':None}
def xyz(v):return [v.x,v.y,v.z]
def tick(_):
    try:
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if s['first'] is None:s['first']=t
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        linear,angular=a.get_root_velocity()
        inp=a.get_editor_property('locomotion_input')
        s['rows'].append({'t':t,'p':xyz(a.get_root_low_point()),'yaw':a.get_actor_rotation().yaw,'v':xyz(linear),'w':xyz(angular),
            'move':xyz(inp.get_editor_property('world_move_input')),'run':inp.get_editor_property('run'),
            'smoothing':smooth.call_method('GetLocomotionRootWindowSmoothing',(a,)),
            'balance':str(lib.call_method('GetRootSelfBalancingState',(a,)))})
        if t-s['first']<8 and time.monotonic()-s['start']<40:return
    except Exception:s['error']=traceback.format_exc()
    unreal.unregister_slate_post_tick_callback(s['cb'])
    out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootImpulseDirection.json'
    out.write_text(json.dumps(s['rows'] if 'error' not in s else s['error']))
    if started_here:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('ROOT_DIRECTION_TRACE',len(s['rows']),s.get('error',''))
s['cb']=unreal.register_slate_post_tick_callback(tick)
if started_here:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
