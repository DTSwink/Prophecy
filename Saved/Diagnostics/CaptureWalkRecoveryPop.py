import unreal,builtins,pathlib,json,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
s={'owned':not bool(ed.get_game_world()),'rows':[],'last':None,'start':None,'wall':time.monotonic(),'h':None}
builtins._calf_connection=s

tag=sys.argv[1] if len(sys.argv)>1 else 'foot-vibration-trace'
w0=ed.get_editor_world()
variant=sys.argv[2] if len(sys.argv)>2 else 'baseline'
old_source=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Tempering.SupportSource')
if variant!='baseline':assert s['owned'],'Ablation needs owned Play'
if variant=='source-off':unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Tempering.SupportSource 0')
trace=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/nn_inputs.jsonl'
start_bytes=trace.stat().st_size if trace.exists() else 0
unreal.SystemLibrary.execute_console_command(w0,'Prophecy.NNInputTraceFrames 330')
out=pathlib.Path(unreal.Paths.project_saved_dir())/('Diagnostics/CalfAnkleConnection-'+tag+'.json')
def v(x):return [x.x,x.y,x.z]
def tr(x):return {'p':v(x.translation),'q':[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w],'s':v(x.scale3d)}
def finish(reason):
    unreal.SystemLibrary.execute_console_command(ed.get_game_world() or w0,'Prophecy.Tempering.SupportSource '+str(old_source))
    unreal.SystemLibrary.execute_console_command(ed.get_game_world() or w0,'Prophecy.NNInputTraceFrames 0')
    if trace.exists():
        with trace.open('rb') as f:
            f.seek(start_bytes)
            (trace.parent.parent/('FootVibration-nn-'+tag+'.jsonl')).write_bytes(f.read())
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
            if not a.is_player_controlled():continue
            if variant=='chain-off' and t>1:unreal.ProphecyLegChainDebugLibrary.set_leg_chain_reconstruction(a,False)
            if variant=='pin-tolerance' and t>1:unreal.ProphecyWalkPinningLibrary.set_walk_pinning_tolerance(a,.1,0.)
            if variant=='pin-soft' and t>1:unreal.ProphecyWalkPinningLibrary.set_walk_pinning_tolerance(a,.1,1.)
            if variant=='pin-tolerance-wide' and t>1:unreal.ProphecyWalkPinningLibrary.set_walk_pinning_tolerance(a,.2,0.)
            if variant in ('pin-reach','pin-reach-off') and t>1:
                lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary'))
                assert lib.call_method('SetWalkPinningReachGuard',args=(a,variant=='pin-reach',6))
            if variant=='no-tempering' and t>1:
                unreal.ProphecyLowerTemperingLibrary.blend_locomotion_lower_body_tempering_to_normal(a,0.,0.,0.,0.)
            if variant=='run' and t>1:
                src=unreal.ProphecyRecoverySource.RUN
                unreal.ProphecyAttackRecoveryLibrary.set_kick_to_locomotion_blend(a,src,1.,1.,src,1.,1.,src,1.,1.)
            row={'t':t,'actor':a.get_name(),'attack':str(a.get_nn_attack_state()),'meshes':{},'targets':{}}
            row['debug_tick']=a.get_editor_property('tick debug')
            if True:
                pin=a.get_locomotion_foot_pinning()
                if pin:row['pinning']={'raw':[pin.raw_network_output.x,pin.raw_network_output.y],
                    'selected':[pin.raw_pinning.x,pin.raw_pinning.y],
                    'effective':[pin.effective_pinning.x,pin.effective_pinning.y],
                    'time':pin.sample_time_seconds,'visible':pin.applies_to_visible_feet}
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
