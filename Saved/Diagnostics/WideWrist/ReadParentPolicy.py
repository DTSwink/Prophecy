import unreal,json
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
state={}
def tick(dt):
    w=sub.get_game_world()
    if not w or unreal.GameplayStatics.get_time_seconds(w)<0.2:return
    result=[]
    lib=unreal.ConstraintInstanceBlueprintLibrary
    for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
        mesh=a.get_pose_reference_mesh()
        if not mesh:continue
        for c in mesh.get_constraints(True):
            names=[str(n) for n in lib.get_attached_body_names(c)[1:]]
            if 'hand_r' in names or 'hand_l' in names:
                result.append({'actor':a.get_name(),'bodies':names,'parent_dominates':str(lib.get_parent_dominates(c))})
    print('WRIST_PARENT_POLICY',json.dumps(result))
    unreal.unregister_slate_post_tick_callback(state['handle'])
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
assert not sub.get_game_world()
state['handle']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
