import unreal,json,pathlib,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackFootSink'
out.mkdir(exist_ok=True)
log=out.parent.parent/'Logs/GameAnimationSample3.log'
s=dict(start=time.monotonic(),last=None,rows=[],events=[],offset=log.stat().st_size,frame=0)
tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.PhysicalFoot.HalfLocomotionLeeway 0')
bones=('pelvis','calf_l','foot_l','calf_r','foot_r')
def xyz(v):return [v.x,v.y,v.z]
def tr(t):return dict(p=xyz(t.translation),q=[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w],s=xyz(t.scale3d))
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    w=ed.get_game_world()
    unreal.SystemLibrary.execute_console_command(w or ed.get_editor_world(),'Prophecy.PhysicalFoot.TraceFrames 0')
    unreal.SystemLibrary.execute_console_command(w or ed.get_editor_world(),'Prophecy.PhysicalFoot.HalfLocomotionLeeway 0')
    with log.open('rb') as f:
        f.seek(s['offset']);(out/(tag+'-drive.log')).write_bytes(b'\n'.join(x for x in f.read().splitlines() if b'FootRecoveryTarget' in x))
    (out/(tag+'.json')).write_text(json.dumps(dict(error=error,rows=s['rows'],events=s['events']),separators=(',',':')))
    if w:level.editor_request_end_play()
    print('ATTACK_FOOT_SINK_DONE',error or 'complete',len(s['rows']))
    s['rows'].clear()
def tick(_):
    try:
        assert time.monotonic()-s['start']<100,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if s['last']==t:return
        s['last']=t
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        s['frame']+=1;f=s['frame']
        if f==1:
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.PhysicalFoot.TraceFrames 650')
            s['events'].append(dict(mode=str(a.get_simulation_mode()),train=int(a.get_editor_property('codex slash train index')),slop=unreal.ProphecyJoltContactSettingsLibrary.get_jolt_penetration_slop(w)))
        r=dict(frame=f,t=t,state=str(a.get_nn_attack_state()),physical={},authored={},meshes={})
        for b in bones:
            p=a.get_physical_body_state(b)
            if p:r['physical'][b]=dict(transform=tr(p[0]),v=xyz(p[1]),sim=p[3])
            p=a.get_authored_body_world_target(b)
            if p:r['authored'][b]=tr(p[2])
        for m in a.get_components_by_class(unreal.SkeletalMeshComponent):
            r['meshes'][m.get_name()]={b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in bones if m.get_bone_index(b)>=0}
        s['rows'].append(r)
        if f==119 and tag=='late':
            unreal.SystemLibrary.execute_console_command(w,'Prophecy.PhysicalFoot.HalfLocomotionLeeway 1')
            s['events'].append(dict(frame=f,change='preserve locomotion ankle allowance on half attacks'))
        if f>=450:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
