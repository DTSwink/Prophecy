import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve existing PIE'
s={'start':time.monotonic(),'frame':0,'rows':[]}
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    level.editor_request_end_play()
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/ObserveResetUpper.json').write_text(json.dumps({'error':error,'rows':s['rows']},indent=2))
    print('RESET_OBSERVATION',error or 'complete')
def tick(_):
    try:
        assert time.monotonic()-s['start']<45,'Timeout'
        w=ed.get_game_world()
        if not w:return
        s['frame']+=1
        if s['frame']<=12 or s['frame'] in (30,60,90,99,100,101,102,110,130,160,200):
            for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
                props=a.get_editor_property('body_magnetization_settings')
                bones={}
                for b in ['head','spine_03','upperarm_l','pelvis','foot_l']:
                    v=next((v for k,v in props.items() if str(k)==b),None)
                    bones[b]=None if v is None else {k:v.get_editor_property(k) for k in ['simulate_body','magnetization_enabled','linear_strength_scale','angular_strength_scale']}
                s['rows'].append({'frame':s['frame'],'actor':a.get_name(),'jolt':a.is_jolt_physical_animation_enabled(),'bones':bones,'profile':unreal.ProphecyPhysicalProfileLibrary.print_physical_bone_profiles(a)})
        if s['frame']>=200:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('Observing existing hit/reset setup for 200 frames without changing gameplay settings.')
