import unreal,builtins,pathlib,json,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
s={'owned':not bool(ed.get_game_world()),'rows':[],'last':None,'start':None,'wall':time.monotonic(),'h':None}
builtins._calf_connection=s
assert s['owned'], 'Isolation requires owned Play'
tag='knee-source-off'
w0=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Tempering.SupportSource 0')
out=pathlib.Path(unreal.Paths.project_saved_dir())/('Diagnostics/CalfAnkleConnection-'+tag+'.json')
def v(x):return [x.x,x.y,x.z]
def tr(x):return {'p':v(x.translation),'q':[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w],'s':v(x.scale3d)}
def finish(reason):
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Tempering.SupportSource 1')
    unreal.unregister_slate_post_tick_callback(s['h'])
    out.write_text(json.dumps({'reason':reason,'owned':s['owned'],'rows':s['rows']},separators=(',',':')))
    print('CALF_CONNECTION_DONE',reason,len(s['rows']))
    if s['owned'] and ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(dt):
    try:
        w=ed.get_game_world()
        if not w:
            if time.monotonic()-s['wall']>20:finish('No world')
            return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        if s['start'] is None:s['start']=t
        for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
            row={'t':t,'actor':a.get_name(),'attack':str(a.get_nn_attack_state()),'meshes':{},'targets':{}}
            for m in a.get_components_by_class(unreal.SkeletalMeshComponent):
                row['meshes'][m.get_name()]={b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in ('pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r') if m.get_bone_index(b)>=0}
            for b in ('pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r'):
                target=a.get_authored_body_world_target(b)
                if target:row['targets'][b]={'previous':tr(target[0]),'future':tr(target[1]),'target':tr(target[2]),'alpha':target[3]}
            s['rows'].append(row)
        if t-s['start']>=10:finish('Complete')
        elif time.monotonic()-s['wall']>180:finish('Timeout')
    except Exception:finish(traceback.format_exc())
s['h']=unreal.register_slate_post_tick_callback(tick)
if s['owned']:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('CALF_CONNECTION_STARTED',s['owned'])
