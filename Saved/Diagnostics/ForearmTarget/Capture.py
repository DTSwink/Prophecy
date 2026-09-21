import unreal,builtins,pathlib,json,time,traceback,sys
mode=sys.argv[1] if len(sys.argv)>1 else 'false'
switch_t=float(sys.argv[2]) if len(sys.argv)>2 else 10
duration=float(sys.argv[3]) if len(sys.argv)>3 else 35
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world()
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/ForearmTarget'
state={'actors':[],'joints':{},'rows':[],'events':[],'last':None,'wall':time.perf_counter(),'switched':False}
builtins._wrist_bool_capture=state
def quat(q):return [q.x,q.y,q.z,q.w]
def vec(v):return [v.x,v.y,v.z]
def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    (p/('capture_'+mode+'.json')).write_text(json.dumps({'reason':reason,'mode':mode,'switch_t':switch_t,'events':state['events'],'rows':state['rows']},separators=(',',':')))
    print('WRIST_BOOL_DONE',mode,reason,len(state['rows']))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(dt):
    try:
        w=sub.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==state['last']:return
        state['last']=t
        if not state['actors']:
            state['actors']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
            if not state['actors']:return
        for a in state['actors']:
            mesh=a.get_pose_reference_mesh()
            if not mesh:continue
            lib=unreal.ConstraintInstanceBlueprintLibrary
            if a.get_name() not in state['joints']:
                cons=mesh.get_constraints(True)
                found={}
                for bone,parent in [('hand_r','lowerarm_r'),('hand_l','lowerarm_l'),('lowerarm_r','upperarm_r'),('lowerarm_l','upperarm_l')]:
                    c=next((c for c in cons if bone in [str(n) for n in lib.get_attached_body_names(c)[1:]] and parent in [str(n) for n in lib.get_attached_body_names(c)[1:]]),None)
                    if c:found[bone]=c
                if len(found)!=4:continue
                state['joints'][a.get_name()]=found
            pose=a.read_nn_future_world_pose()
            if not pose:continue
            names,future,presented,alpha=pose; lookup={str(n):i for i,n in enumerate(names)}
            row={'t':t,'actor':a.get_name(),'player':str(a.get_controller()),'prediction':a.is_jolt_joint_limit_prediction_enabled(),'jolt':a.is_jolt_physical_animation_enabled(),'bones':{},'limits':{b:str(lib.get_angular_limits(c)[1:]) for b,c in state['joints'][a.get_name()].items()}}
            for bone in ('hand_r','lowerarm_r','upperarm_r','hand_l','lowerarm_l','upperarm_l'):
                body=a.get_physical_body_state(bone)
                if body and bone in lookup:
                    tr,lin,ang,sim=body
                    row['bones'][bone]={'q':quat(tr.rotation),'p':vec(tr.translation),'w':vec(ang),'target':quat(presented[lookup[bone]].rotation),'target_p':vec(presented[lookup[bone]].translation),'sim':sim}
            state['rows'].append(row)
        if t>=duration:finish('Complete')
        elif time.perf_counter()-state['wall']>240:finish('Timeout')
    except Exception:finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('WRIST_BOOL_START',mode,switch_t,duration)
