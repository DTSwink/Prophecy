import pathlib, time, traceback
import unreal

root = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics'
scope = {'__name__': '__continuous_presentation_validation__'}
exec(compile((root/'PelvisBackward/capture_live.py').read_text(encoding='utf-8'), 'capture_live.py','exec'),scope)
state=scope['state']
unreal.unregister_slate_post_tick_callback(state['handle'])
state['handle']=None
state['duration']=65.0
state['path']=str(root/'PelvisBackwardReview'/('continuous-'+time.strftime('%H%M%S')+'.json'))
state['injections']=[]
state['settings_modified']=False
original_tick=scope['tick']
original_finish=scope['finish']

def finish(reason):
    agent=state['actor']
    if agent:
        state['final_settings']={
            'feedback':str(agent.get_physical_feedback_tolerance('pelvis')),
            'self_collision_hand_head':str(agent.get_jolt_body_pair_self_collision_enabled('hand_l','head')),
            'sword':str(agent.get_held_sword()),
            'input':str(agent.get_editor_property('locomotion_input'))}
    original_finish(reason)
scope['finish']=finish
state['finish']=finish

def tick(dt):
    try:
        count=len(state['rows'])
        original_tick(dt)
        if state['done']: return
        if len(state['rows'])>count:
            world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            camera=unreal.GameplayStatics.get_player_camera_manager(world,0)
            if camera:
                state['rows'][-1]['camera']=scope['vec'](camera.get_camera_location())
        if state['first_time'] is not None and len(state['injections'])<24:
            elapsed=state['last_time']-state['first_time']
            if elapsed>=6.0+1.7*len(state['injections']):
                delay=(.035,.043,.052,.069,.072,.095)[len(state['injections'])%6]
                before=time.perf_counter()
                time.sleep(delay)
                state['injections'].append(dict(after_t=state['last_time'],requested=delay,actual=time.perf_counter()-before))
    except Exception:
        state['error']=traceback.format_exc()
        finish('Validation error')
state['handle']=unreal.register_slate_post_tick_callback(tick)
print('CONTINUOUS_VALIDATION_STARTED',state['path'],'24 hitches; saved gameplay settings retained')
