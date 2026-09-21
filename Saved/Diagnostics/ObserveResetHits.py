import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user PIE'
s={'start':time.monotonic(),'frame':0,'actors':[],'callbacks':[],'events':[],'flags':[]}
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if ed.get_game_world():level.editor_request_end_play()
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/ResetHits.json').write_text(json.dumps({k:s[k] for k in ['events','flags']}|{'error':error},indent=2))
    print('RESET_HIT_OBSERVATION',error or 'complete',len(s['events']))
def tick(_):
    try:
        assert time.monotonic()-s['start']<60,'Timeout'
        w=ed.get_game_world()
        if not w:return
        s['frame']+=1
        if not s['actors']:
            s['actors']=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
            for a in s['actors']:
                def onhit(me,other,impulse,hit):
                    s['events'].append({'frame':s['frame'],'agent':me.get_name(),'other':other.get_name() if other else '', 'my_bone':str(hit.my_bone_name),'other_bone':str(hit.bone_name)})
                a.on_actor_hit.add_callable(onhit)
                s['callbacks'].append(onhit)
        if s['frame'] in (1,6,30,90,110,130,200,300):
            for a in s['actors']:
                mesh=next(c for c in a.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name()=='PhysicalMesh')
                s['flags'].append({'frame':s['frame'],'agent':a.get_name(),'agent_enabled':a.get_editor_property('generate_physical_hit_events'),'component_enabled':mesh.get_editor_property('body_instance').get_editor_property('notify_rigid_body_collision'),'jolt':a.is_jolt_physical_animation_enabled()})
        if s['frame']>=300:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('Observing actual Actor Hit delivery before/after Blueprint reset; gameplay unchanged.')
