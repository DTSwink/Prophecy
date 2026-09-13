"""Short ABBA PIE comparison; existing testNN agents, no asset/settings saves."""
import json, math, statistics, time, traceback
from pathlib import Path
import unreal

editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert editor.get_game_world() is None, 'End the current play session first'
order=globals().get('ORDER',['HalfSim','Physical','Physical','HalfSim'])
warmup=globals().get('WARMUP',3)
sample_seconds=globals().get('SAMPLE_SECONDS',7)
state={'index':0,'phase':'wait_world','rows':[],'handle':None,'started':time.perf_counter()}
output=Path(unreal.Paths.project_saved_dir()).resolve()/'Benchmarks'/globals().get('OUTPUT','half_sim_vs_sim_quick.json')

def finish(error=None):
    if state['handle'] is not None:unreal.unregister_slate_post_tick_callback(state['handle']);state['handle']=None
    levels.editor_request_end_play()
    result={'error':error,'warmup_seconds':warmup,'sample_seconds':sample_seconds,'order':order,
            'method':'Fresh PIE per pass; existing testNN agents and Blueprint motion, same starting camera; actual idle/falling behavior, not equal-motion CPU microbenchmark.',
            'passes':state['rows'],'summary':{}}
    for mode in ['HalfSim','Physical']:
        frames=[x for row in state['rows'] if row['mode']==mode for x in row['frames_ms']]
        cpu=[x for row in state['rows'] if row['mode']==mode for x in row['world_tick_samples_ms']]
        if frames:result['summary'][mode]={'frames':len(frames),'mean_frame_ms':statistics.mean(frames),
            'fps':1000/statistics.mean(frames),'median_frame_ms':statistics.median(frames),
            'p95_frame_ms':sorted(frames)[int(.95*(len(frames)-1))],
            'mean_world_tick_ms':statistics.mean(cpu) if cpu else None}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2))
    unreal.log('Quick mode benchmark: '+str(output)+' error='+str(error))

def tick(dt):
    try:
        if time.perf_counter()-state['started']>100:raise RuntimeError('Benchmark watchdog')
        world=editor.get_game_world()
        if state['phase']=='wait_end':
            if world is None:
                levels.editor_request_begin_play();state['phase']='wait_world'
            return
        if world is None:return
        now=time.perf_counter()
        if state['phase']=='wait_world':
            agents=[a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
            if not agents:return
            for a in agents:
                a.stop_nn_attack()
                unreal.SystemLibrary.execute_console_command(world,'ke '+a.get_path_name()+' SetSimulationMode '+order[state['index']])
            unreal.AutomationLibrary.enable_stat_group(world,'Game')
            state.update(phase='warm',warm_start=now,agents=agents)
            return
        if state['phase']=='warm':
            if now-state['warm_start']<warmup:return
            row={'mode':order[state['index']],'agents':len(state['agents']),'frames_ms':[],'world_tick_samples_ms':[]}
            state['rows'].append(row);state.update(phase='sample',sample_start=now,last=now,stat_last=0.)
            return
        if state['phase']=='sample':
            row=state['rows'][-1]
            row['frames_ms'].append((now-state['last'])*1000);state['last']=now
            if now-state['stat_last']>.25:
                actual=[str(a.get_simulation_mode()) for a in state['agents']]
                assert all(order[state['index']].upper() in n.upper().replace('_','') for n in actual),actual
                row['verified_modes']=actual
                row['world_tick_samples_ms'].append(unreal.AutomationLibrary.get_stat_inc_average('STAT_WorldTickTime'))
                state['stat_last']=now
            if now-state['sample_start']<sample_seconds:return
            row['mean_frame_ms']=statistics.mean(row['frames_ms']);row['fps']=1000/row['mean_frame_ms']
            unreal.AutomationLibrary.disable_stat_group(world,'Game')
            levels.editor_request_end_play();state['index']+=1
            if state['index']==len(order):finish();return
            state['phase']='wait_end'
    except Exception:finish(traceback.format_exc())

levels.editor_request_begin_play()
state['handle']=unreal.register_slate_post_tick_callback(tick)
print('Half Sim / Sim ABBA test scheduled, approximately 45 seconds')
