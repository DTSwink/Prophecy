import unreal,pathlib,json,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
tag=sys.argv[1] if len(sys.argv)>1 else 'before'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/KinematicFlicker';out.mkdir(exist_ok=True)
s=dict(start=time.monotonic(),last=None,rows=[],frame=0)
bones=('root','pelvis','spine_03','head','hand_l','hand_r','foot_l','foot_r')
def tr(t):return dict(p=[t.translation.x,t.translation.y,t.translation.z],q=[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w])
def finish(error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    (out/(tag+'.json')).write_text(json.dumps(dict(error=error,rows=s['rows']),separators=(',',':')))
    print('KINEMATIC_FLICKER_DONE',error or 'complete',len(s['rows']))
    s['rows'].clear()
    if ed.get_game_world():level.editor_request_end_play()
def tick(_):
    try:
        assert time.monotonic()-s['start']<60,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t;s['frame']+=1
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        if s['frame']>=95:
            r=dict(frame=s['frame'],tick=int(a.get_editor_property('tick debug')),t=t,state=str(a.get_nn_attack_state()),meshes={},pose={})
            names,future,presented,alpha=a.read_nn_future_world_pose()
            r['alpha']=alpha;r['pose']={str(n):dict(future=tr(f),presented=tr(p)) for n,f,p in zip(names,future,presented) if str(n) in bones}
            actors=[a]+list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyNNLocomotionManager))
            for actor in actors:
                for m in actor.get_components_by_class(unreal.SkinnedMeshComponent):
                    if actor!=a and not m.get_name().endswith('_'+str(a.get_agent_handle().index)):continue
                    r['meshes'][m.get_name()]=dict(world=tr(m.get_world_transform()),visible=m.is_visible(),bones={b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in bones if m.get_bone_index(b)>=0})
            s['rows'].append(r)
        if s['frame']>=180:finish()
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
