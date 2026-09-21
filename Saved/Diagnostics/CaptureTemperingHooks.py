import unreal, pathlib, json, time, sys
disable_second = '--disable-second' in sys.argv
disable_gap = '--disable-gap' in sys.argv
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve existing user PIE'
out=pathlib.Path(unreal.Paths.project_saved_dir())/('Diagnostics/TemperingHooksGap' if disable_gap else 'Diagnostics/TemperingHooksDisabled' if disable_second else 'Diagnostics/TemperingHooks')
out.mkdir(parents=True,exist_ok=True)
sources={'slash':pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/live_steps.jsonl',
         'nn':pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/nn_inputs.jsonl'}
offsets={k:p.stat().st_size if p.exists() else 0 for k,p in sources.items()}
old={k:unreal.SystemLibrary.get_console_variable_int_value(k) for k in ['Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames','Prophecy.NNInputTraceFrames']}
for k,v in {'Prophecy.SlashTraceAgent':-2,'Prophecy.SlashTraceFrames':360,'Prophecy.NNInputTraceFrames':240}.items():
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),f'{k} {v}')
s={'rows':[],'start':time.monotonic(),'frames':0,'actors':None,'disabled':[]}
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    for k,v in old.items():unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),f'{k} {v}')
    (out/'visible.json').write_text(json.dumps({'error':error,'rows':s['rows']},default=str))
    for k,p in sources.items():
        if p.exists():
            with p.open('rb') as f:f.seek(offsets[k]);data=f.read()
            (out/(k+'.jsonl')).write_bytes(data)
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    (out/'done.json').write_text(json.dumps({'frames':s['frames'],'rows':len(s['rows']),'error':error,'disabled':s['disabled']}))
def tick(_):
    try:
        w=ed.get_game_world()
        if not w:
            if time.monotonic()-s['start']>50:finish('PIE did not start')
            return
        if s['actors'] is None:s['actors']=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
        t=unreal.GameplayStatics.get_time_seconds(w)
        for a in s['actors']:
            attack=a.get_nn_attack_state()
            if ((disable_second and t>3.9 and attack) or (disable_gap and t>2.7)) and a.get_name() not in [x[0] for x in s['disabled']]:
                unreal.ProphecyLowerTemperingLibrary.set_locomotion_lower_body_tempering(a,False)
                s['disabled'].append([a.get_name(),t,str(attack)])
            mesh=a.get_pose_reference_mesh()
            def xyz(v):return [v.x,v.y,v.z]
            s['rows'].append({'time':t,'tick':s['frames'],'actor':a.get_name(),'attack':a.get_nn_attack_state(),
                'mode':str(a.get_simulation_mode()),'root':xyz(a.get_actor_location()),
                'bones':{b:xyz(mesh.get_socket_location(b)) for b in ['pelvis','foot_l','foot_r','hand_l','hand_r','head']}})
        s['frames']+=1
        if s['frames']>=360 or time.monotonic()-s['start']>50:finish()
    except Exception as exc:finish(str(exc))
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('Short current-scene capture started; ends its own PIE and restores trace settings.')
