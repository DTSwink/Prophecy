import unreal, builtins, pathlib, json, time, traceback
sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world(), 'Start outside PIE'
out = pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordNNInput'
out.mkdir(parents=True, exist_ok=True)
state = dict(handle=None, stage=-1, next=2.0, actor=None, rows=[], wall=time.perf_counter())
builtins._sword_nn_input_check = state
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    (out/'result.json').write_text(json.dumps(dict(passed=error is None, error=error, rows=state['rows']), indent=2))
    print('SWORD_NN_INPUT_CHECK', error or 'PASS')
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(dt):
    try:
        if time.perf_counter()-state['wall']>90: raise RuntimeError('Timed out')
        world=sub.get_game_world()
        if not world: return
        t=unreal.GameplayStatics.get_time_seconds(world)
        if t<state['next']: return
        stage=state['stage']
        if stage==-1:
            actors=list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent))
            assert actors, 'No test agents'
            state['actor']=actors[-1]
            state['actor'].hide_sword()
            # Deliberately wrong legacy input must be replaced during NN encoding.
            state['actor'].set_upper_nn_inputs(True, 0.0, 0.0)
        else:
            a=state['actor']
            expected=[False,True,False,True,False,True,False][stage]
            actual=a.get_editor_property('upper_nn_has_sword')
            state['rows'].append(dict(stage=stage, held=bool(a.get_held_sword()), input=actual, expected=expected, simulated=a.is_sword_simulated()))
            assert actual==expected, 'Unexpected NN sword input: '+str(state['rows'][-1])
            if stage==0:
                assert a.equip_sword(False), 'Attached equip failed'
                a.set_upper_nn_inputs(False, 0.0, 0.0)
            elif stage==1: assert a.drop_sword(), 'Drop failed'
            elif stage==2: assert a.equip_sword(True), 'Simulated equip failed'
            elif stage==3: a.hide_sword()
            elif stage==4: assert a.equip_sword(False), 'Second attached equip failed'
            elif stage==5: a.get_held_sword().destroy_actor()
            else:
                finish()
                return
        state['stage']+=1
        state['next']=t+0.5
    except Exception: finish(traceback.format_exc())
state['handle']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('SWORD_NN_INPUT_CHECK_STARTED')
