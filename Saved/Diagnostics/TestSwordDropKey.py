import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordDropKey'
folder.mkdir(parents=True,exist_ok=True)
s={'phase':'stop','start':time.monotonic(),'frame':0,'rows':[]}
def audit(w):
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.MeshAudit A_Sword')
    return json.loads((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/DefaultJoltMeshes/World.json').read_text(encoding='utf-8-sig'))
def finish(result,error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    w=ed.get_game_world()
    if w:
        unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.DebugDropKey release')
        level.editor_request_end_play()
    (folder/'PIE.json').write_text(json.dumps({'result':result,'error':error,'rows':s['rows']},indent=2))
    print('SWORD_DROP_KEY_TEST',result,error)
def tick(_):
    try:
        assert time.monotonic()-s['start']<65,'Timeout'
        s['frame']+=1
        w=ed.get_game_world()
        if s['phase']=='stop':
            if w:return
            s['phase']='start';level.editor_request_begin_play();return
        if not w:return
        if s['phase']=='start':
            if unreal.GameplayStatics.get_time_seconds(w)<.6:return
            a=unreal.GameplayStatics.get_player_pawn(w,0)
            sword=a.get_held_sword()
            assert sword,'No held sword before key'
            s['sword']=sword.get_path_name()
            before=audit(w);assert not before['shared_stopped'],before['shared_error']
            s['steps']=before['completed_steps'];s['rows'].append({'before':before})
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.DebugDropKey press')
            s['pressed_frame']=s['frame'];s['phase']='pressed';return
        if s['phase']=='pressed' and s['frame']>=s['pressed_frame']+3:
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.DebugDropKey release')
            a=unreal.GameplayStatics.get_player_pawn(w,0)
            assert not a.get_held_sword(),'Right Shift did not drop the sword'
            s['phase']='released'
        if s['phase']=='released' and s['frame']>=s['pressed_frame']+45:
            after=audit(w);s['rows'].append({'after':after})
            assert not after['shared_stopped'],after['shared_error']
            assert after['completed_steps']>s['steps']+10,'Shared physics did not keep advancing'
            meshes=[m for m in after['meshes'] if m['component'].startswith(s['sword']+'.')]
            assert len(meshes)==1 and meshes[0]['jolt'] and meshes[0]['jolt_dynamic'],meshes
            assert meshes[0]['active_owners']==1 and meshes[0]['pending_owners']==0,meshes
            finish('passed')
    except Exception:finish('failed',traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if ed.get_game_world():level.editor_request_end_play()
