import unreal, pathlib, json, time
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user PIE'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/recovered_profile_print.json'
s={'frames':0,'started':time.monotonic(),'rows':{},'actors':[]}
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(s['callback'])
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    out.write_text(json.dumps({'frames':s['frames'],'rows':s['rows'],'error':error}))
def tick(_):
    try:
        world=ed.get_game_world()
        if not world:
            if time.monotonic()-s['started']>60:finish('PIE did not start')
            return
        if not s['actors']:
            s['actors']=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent)
        for actor in s['actors']:
            text=unreal.ProphecyPhysicalProfileLibrary.print_physical_bone_profiles(actor)
            lines=text.splitlines()
            assert lines and lines[0].startswith('head : ')
            assert lines[-1].startswith(('foot_','ball_'))
            assert 'cm' not in text and 'deg' not in text
            s['rows'][actor.get_name()]=len(lines)
        s['frames']+=1
        if s['frames']>=60:finish()
    except Exception as exc:finish(str(exc))
s['callback']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('Started bounded 60-frame PIE check; will end only its own play session.')
