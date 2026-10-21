"""User-requested visual Play with transient 10/32 iterations after first cut.
Leaves Play running for the user. No assets, camera, speed or Blueprint edits.
"""
import json, pathlib, time, traceback, unreal
show_ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
show_le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not show_ed.get_game_world(), 'Existing user Play left untouched'
show_out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PikeSlide/show-iterations.json'
show_state={'start':time.monotonic(),'handle':None,'world':None}
def show_finish(status,**details):
    unreal.unregister_slate_post_tick_callback(show_state['handle'])
    show_out.write_text(json.dumps({'status':status,'velocity_iterations':10,'position_iterations':32,
        'play_left_running':bool(show_ed.get_game_world()),**details},indent=2))
def show_tick(dt):
    try:
        w=show_ed.get_game_world()
        if not w:
            if show_state['world']:show_finish('Play ended before cut')
            elif time.monotonic()-show_state['start']>30:show_finish('Play startup timeout')
            return
        if not show_state['world']:show_state['world']=w
        if w!=show_state['world']:show_finish('Original Play world changed');return
        for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
            if not a.get_class().get_name().startswith('A_Sword_C') or not a.get_editor_property('cuts'):continue
            for c in a.get_components_by_class(unreal.PhysicsConstraintComponent):
                if c.get_name()=='dont':continue
                comps=c.get_constrained_components()
                victim=next((x for x in (comps[0],comps[2]) if isinstance(x,unreal.SkeletalMeshComponent)),None)
                if not victim:continue
                p=victim.get_socket_location('hand_r')
                suffix=' at %.9f %.9f %.9f'%(p.x,p.y,p.z)
                unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ContactExperiment iterations 10 32'+suffix)
                unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ContactExperiment capture pikeslide_show32'+suffix)
                show_finish('applied',game_time=unreal.GameplayStatics.get_time_seconds(w),victim=victim.get_path_name())
                return
        if time.monotonic()-show_state['start']>60:show_finish('No skeletal cut found within timeout')
    except Exception:show_finish('error',error=traceback.format_exc())
show_out.write_text(json.dumps({'status':'waiting for first skeletal cut'}))
show_state['handle']=unreal.register_slate_post_tick_callback(show_tick)
show_le.editor_request_begin_play()
print('Visual Play started; temporary 10/32 iterations will apply at the first cut and Play will remain running.')
