import unreal, builtins, pathlib, json
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world()
state={'handle':None}
builtins._forearm_axis=state
def run(dt):
    w=sub.get_game_world()
    if not w or unreal.GameplayStatics.get_time_seconds(w)<3: return
    unreal.unregister_slate_post_tick_callback(state['handle'])
    result=[]
    lib=unreal.ConstraintInstanceBlueprintLibrary
    for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
        mesh=a.get_pose_reference_mesh()
        joints=[c for c in mesh.get_constraints(True) if set(str(n) for n in lib.get_attached_body_names(c)[1:])=={'lowerarm_r','upperarm_r'}]
        result.append({'actor':a.get_name(),'jolt':a.is_jolt_physical_animation_enabled(),
          'current_limits':str(lib.get_angular_limits(joints[0])[1:]),
          'request_1_180_180':str(a.set_physical_joint_angular_limits('lowerarm_r',unreal.AngularConstraintMotion.ACM_LIMITED,1.,unreal.AngularConstraintMotion.ACM_LIMITED,180.,unreal.AngularConstraintMotion.ACM_LIMITED,180.))})
    p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/ForearmAxis'
    p.mkdir(exist_ok=True,parents=True)
    (p/'inspection.json').write_text(json.dumps(result,indent=2))
    print('FOREARM_AXIS_INSPECTION',json.dumps(result))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
state['handle']=unreal.register_slate_post_tick_callback(run)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
