import unreal,builtins,pathlib,json
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world()
state={};builtins._wrist_meta=state
def tick(dt):
    w=sub.get_game_world()
    if not w or unreal.GameplayStatics.get_time_seconds(w)<0.5:return
    result=[]
    for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
        result.append({'name':a.get_name(),'controller':str(a.get_controller()),
            'feedback':{b:str(a.get_physical_feedback_tolerance(b)) for b in ('hand_r','lowerarm_r','upperarm_r','hand_l')},
            'magnetization':{b:str(a.get_body_magnetization_settings(b)) for b in ('hand_r','lowerarm_r','upperarm_r','hand_l')}})
    (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/WideWrist/metadata.json').write_text(json.dumps(result,indent=2))
    print('WRIST_METADATA',result)
    unreal.unregister_slate_post_tick_callback(state['handle'])
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
state['handle']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
