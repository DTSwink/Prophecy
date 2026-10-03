import unreal,time,json,pathlib,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
cls=unreal.load_class(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent_C')
state={'owned':not bool(ed.get_game_world()),'start':time.monotonic(),'frames':0}
def finish(result):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/MissingCharacters-20261002/play-check.json').write_text(json.dumps(result,indent=2))
    if state['owned'] and ed.get_game_world():level.editor_request_end_play()
    print('RESTORED_CHARACTER_PLAY_CHECK',json.dumps(result))
def tick(dt):
    try:
        world=ed.get_game_world()
        if world:
            state['frames']+=1
            if state['frames']>=40:
                rows=[]
                for actor in unreal.GameplayStatics.get_all_actors_of_class(world,cls):
                    data=actor.read_nn_future_world_pose()
                    meshes=[m for m in actor.get_components_by_class(unreal.SkinnedMeshComponent) if m.is_visible()]
                    rows.append({'actor':actor.get_name(),'player':actor.is_player_controlled(),'pose_bones':len(data[0]) if data else 0,'visible_meshes':len(meshes)})
                finish({'ok':len(rows)==3 and any(r['player'] and r['pose_bones']>0 and r['visible_meshes']>0 for r in rows),'actors':rows,'owned_play':state['owned']})
                return
        if time.monotonic()-state['start']>40:finish({'ok':False,'error':'timeout'})
    except Exception:finish({'ok':False,'error':traceback.format_exc()})
state['handle']=unreal.register_slate_post_tick_callback(tick)
if state['owned']:level.editor_request_begin_play()
print('RESTORED_CHARACTER_CHECK_STARTED','owned',state['owned'])
