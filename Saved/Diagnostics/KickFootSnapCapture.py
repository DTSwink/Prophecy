import unreal, builtins, pathlib, json, time, traceback, sys
mode=sys.argv[1] if len(sys.argv)>1 else 'current'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
s={'owned':not bool(ed.get_game_world()),'rows':[],'last':None,'start':None,'wall':time.monotonic(),'h':None,'modified':set()}
assert mode=='current' or s['owned'], 'Experiments require a new diagnostic Play session'
builtins._kick_foot_snap=s
out=pathlib.Path(unreal.Paths.project_saved_dir())/('Diagnostics/KickFootSnap'+('' if mode=='current' else '-'+mode)+'.json')
def v(x):return [x.x,x.y,x.z]
def tr(x):return {'p':v(x.translation),'q':[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w]}
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['h'])
    out.write_text(json.dumps({'reason':reason,'owned':s['owned'],'rows':s['rows']},separators=(',',':')))
    print('KICK_FOOT_CAPTURE_DONE',reason,len(s['rows']))
    if s['owned'] and ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(dt):
    try:
        w=ed.get_game_world()
        if not w:
            if time.monotonic()-s['wall']>15:finish('No world')
            return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last']:return
        s['last']=t
        if s['start'] is None:s['start']=t
        for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
            if mode=='no_reconstruction' and t>1 and a.get_name() not in s['modified']:
                assert unreal.ProphecyLegChainDebugLibrary.set_leg_chain_reconstruction(a,False)
                s['modified'].add(a.get_name())
            row={'t':t,'actor':a.get_name(),'attack':str(a.get_nn_attack_state()),'bones':{}}
            for b in ('pelvis','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r'):
                body=a.get_physical_body_state(b)
                target=a.get_authored_body_world_target(b)
                r={}
                if body:r.update(physical=tr(body[0]),velocity=v(body[1]),sim=body[3])
                if target:r.update(previous=tr(target[0]),future=tr(target[1]),target=tr(target[2]),alpha=target[3])
                row['bones'][b]=r
            s['rows'].append(row)
        if t-s['start']>=(24 if mode in ('current','fixed') else 7):finish('Complete')
        elif time.monotonic()-s['wall']>180:finish('Wall timeout')
    except Exception:finish(traceback.format_exc())
s['h']=unreal.register_slate_post_tick_callback(tick)
if s['owned']:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('KICK_FOOT_CAPTURE_STARTED',s['owned'])
