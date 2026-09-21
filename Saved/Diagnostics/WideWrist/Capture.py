import unreal,builtins,pathlib,json,time,traceback,sys
mode=sys.argv[1] if len(sys.argv)>1 else 'current'
duration=float(sys.argv[2]) if len(sys.argv)>2 else 30
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world()
state={'actors':[],'joints':{},'rows':[],'last':None,'start':None,'wall':time.perf_counter(),'handle':None}
builtins._wide_wrist=state
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/WideWrist';p.mkdir(exist_ok=True,parents=True)
def quat(q): return [q.x,q.y,q.z,q.w]
def vec(v): return [v.x,v.y,v.z]
def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    (p/(mode+'.json')).write_text(json.dumps({'reason':reason,'rows':state['rows']},separators=(',',':')))
    print('WIDE_WRIST_DONE',mode,reason,len(state['rows']))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(dt):
    try:
        w=sub.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==state['last']:return
        state['last']=t
        if not state['actors']:
            if t<2:return
            state['start']=t
            state['actors']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
            for a in state['actors']:
                if mode=='free':
                    for b in ('hand_l','hand_r'):
                        a.set_physical_joint_angular_limits(b,unreal.AngularConstraintMotion.ACM_FREE,180,unreal.AngularConstraintMotion.ACM_FREE,180,unreal.AngularConstraintMotion.ACM_FREE,180)
                if mode in ('swing_only','twist_only'):
                    limited=unreal.AngularConstraintMotion.ACM_LIMITED;free=unreal.AngularConstraintMotion.ACM_FREE
                    for b in ('hand_l','hand_r'):
                        a.set_physical_joint_angular_limits(b,limited if mode=='swing_only' else free,170,limited if mode=='swing_only' else free,170,limited if mode=='twist_only' else free,170)
                mesh=a.get_pose_reference_mesh();lib=unreal.ConstraintInstanceBlueprintLibrary
                state['joints'][a.get_name()]={b:next(c for c in mesh.get_constraints(True) if b in [str(n) for n in lib.get_attached_body_names(c)[1:]] and parent in [str(n) for n in lib.get_attached_body_names(c)[1:]]) for b,parent in [('hand_r','lowerarm_r'),('hand_l','lowerarm_l'),('lowerarm_r','upperarm_r'),('lowerarm_l','upperarm_l')]}
        for a in state['actors']:
            pose=a.read_nn_future_world_pose()
            if not pose:continue
            names,future,presented,alpha=pose; lookup={str(n):i for i,n in enumerate(names)}
            row={'t':t,'actor':a.get_name(),'player':str(a.get_controller()),'bones':{},'limits':{b:str(unreal.ConstraintInstanceBlueprintLibrary.get_angular_limits(c)[1:]) for b,c in state['joints'][a.get_name()].items()}}
            for b in ('hand_r','lowerarm_r','upperarm_r','hand_l','lowerarm_l','upperarm_l'):
                body=a.get_physical_body_state(b)
                if body and b in lookup:
                    tr,lin,ang,sim=body
                    row['bones'][b]={'q':quat(tr.rotation),'w':vec(ang),'p':vec(tr.translation),'target':quat(presented[lookup[b]].rotation)}
            state['rows'].append(row)
        if t-state['start']>=duration:finish('Complete')
        elif time.perf_counter()-state['wall']>240:finish('Timeout')
    except Exception:finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('WIDE_WRIST_START',mode)
