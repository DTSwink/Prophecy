import unreal, pathlib, json, time, traceback
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
s = {'start': time.monotonic()}
def tick(_):
    try:
        assert time.monotonic()-s['start']<60, 'PIE timeout'
        world=ed.get_game_world()
        if not world or unreal.GameplayStatics.get_time_seconds(world)<1: return
        managers=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyNNLocomotionManager)
        assert managers, 'No manager'
        rows=[]
        for m in managers:
            assert m.is_actor_tick_enabled(), 'NN manager initialization failed'
            model=m.get_editor_property('upper_onnx_model_path')
            assert model.replace('\\','/').endswith('Content/locomotion/NN/prophecy_upper_body_b100.onnx'), model
            rows.append({'manager':m.get_path_name(),'model':model})
        result={'result':'passed','managers':rows}
    except Exception:
        result={'result':'failed','error':traceback.format_exc()}
    unreal.unregister_slate_post_tick_callback(s['cb'])
    (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/UpperCheckpoint20260915/PIE.json').write_text(json.dumps(result,indent=2))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('UPPER_CHECKPOINT_SMOKE',json.dumps(result))
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
