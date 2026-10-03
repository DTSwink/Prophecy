"""100 real NN lanes and physics agents. PIE-only, no production layout changes."""
import unreal, json, statistics, time, traceback
from pathlib import Path
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert editor.get_game_world() is None
order=globals().get('ORDER',['HalfSim','Physical','Physical','HalfSim'])
warmup=globals().get('WARMUP',5.)
duration=globals().get('DURATION',8.)
out=Path(unreal.Paths.project_saved_dir()).resolve()/'Benchmarks'/globals().get('OUTPUT','100_agent_modes.json')
state={'phase':'wait_world','index':0,'rows':[],'started':time.perf_counter(),'handle':None}

def finish(error=None):
    if state['handle'] is not None:unreal.unregister_slate_post_tick_callback(state['handle']);state['handle']=None
    world=editor.get_game_world()
    if world:unreal.AutomationLibrary.disable_stat_group(world,'Game')
    levels.editor_request_end_play()
    summary={}
    for mode in set(order):
        rows=[r for r in state['rows'] if r['mode']==mode]
        frames=[x for r in rows for x in r['frames_ms']]
        cpu=[x for r in rows for x in r['world_tick_ms']]
        if frames:summary[mode]={'frames':len(frames),'fps':1000/statistics.mean(frames),
            'mean_frame_ms':statistics.mean(frames),'median_frame_ms':statistics.median(frames),
            'p95_frame_ms':sorted(frames)[int(.95*(len(frames)-1))],
            'world_tick_ms':statistics.mean(cpu) if cpu else None}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'error':error,'warmup_seconds':warmup,'duration_seconds':duration,
        'setup':'100 registered Blueprint agents, stationary intent, 30 Hz batched NN, grid, shared camera, LOD0 and no shadows. Half Sim on Mesh with extra PhysicalMesh empty/disabled and manual follower tick off. Sim retains current Blueprint follower on PhysicalMesh.',
        'passes':state['rows'],'summary':summary},indent=2))
    unreal.log('100-agent benchmark finished: '+str(error))

def audit(agents,mode):
    assert len(agents)==100,len(agents)
    positions=[]
    result={'registered_agents':len(agents),'active_meshes':0,'simulating_meshes':0,'disabled_extra_meshes':0,'actor_ticks':0,'active_mesh_names':{}}
    for a in agents:
        assert mode.upper() in str(a.get_simulation_mode()).upper().replace('_',''),str(a.get_simulation_mode())
        active=a.get_pose_reference_mesh()
        assert active.get_skeletal_mesh_asset() and active.is_component_tick_enabled()
        assert active.is_simulating_physics('pelvis')
        p=active.get_socket_location('pelvis');positions.append([p.x,p.y,p.z])
        assert active.get_name()==('Mesh' if mode=='HalfSim' else 'PhysicalMesh'),active.get_name()
        result['active_mesh_names'][active.get_name()]=result['active_mesh_names'].get(active.get_name(),0)+1
        result['actor_ticks']+=int(a.is_actor_tick_enabled())
        for m in a.get_components_by_class(unreal.SkeletalMeshComponent):
            result['active_meshes']+=int(m.get_skeletal_mesh_asset() is not None)
            result['simulating_meshes']+=int(m.is_simulating_physics('pelvis'))
            if m!=active:
                assert m.get_skeletal_mesh_asset() is None,m.get_path_name()
                assert not m.is_component_tick_enabled(),m.get_path_name()
                assert not m.is_simulating_physics('pelvis'),m.get_path_name()
                result['disabled_extra_meshes']+=1
    assert result['active_meshes']==100 and result['simulating_meshes']==100,result
    result['pelvis_positions_cm']=positions
    result['pelvis_bounds_cm']=[[min(p[i] for p in positions),max(p[i] for p in positions)] for i in range(3)]
    return result

def tick(dt):
    try:
        if time.perf_counter()-state['started']>240:raise RuntimeError('Benchmark watchdog')
        world=editor.get_game_world()
        if state['phase']=='wait_end':
            if world is None:levels.editor_request_begin_play();state['phase']='wait_world'
            return
        if not world:return
        now=time.perf_counter()
        if state['phase']=='wait_world':
            if not any(a.has_valid_agent_handle() for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent)):return
            unreal.SystemLibrary.execute_console_command(world,'Prophecy.HalfSimBench.Prepare '+order[state['index']])
            state.update(phase='settle',prepared=time.perf_counter())
            return
        if state['phase']=='settle':
            if now-state['prepared']<.5:return
            agents=[a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
            row={'mode':order[state['index']],'audit_before':audit(agents,order[state['index']]),'frames_ms':[],'world_tick_ms':[]}
            state['rows'].append(row)
            unreal.AutomationLibrary.enable_stat_group(world,'Game')
            state.update(phase='warm',warm_start=now,agents=agents)
            return
        if state['phase']=='warm':
            if now-state['warm_start']<warmup:return
            state.update(phase='sample',sample_start=now,last=now,stats_last=0.)
            return
        if state['phase']=='sample':
            row=state['rows'][-1]
            row['frames_ms'].append((now-state['last'])*1000);state['last']=now
            if now-state['stats_last']>.5:
                row['world_tick_ms'].append(unreal.AutomationLibrary.get_stat_inc_average('STAT_WorldTickTime'))
                state['stats_last']=now
            if now-state['sample_start']<duration:return
            row['audit_after']=audit(state['agents'],row['mode'])
            row['fps']=1000/statistics.mean(row['frames_ms'])
            unreal.AutomationLibrary.disable_stat_group(world,'Game')
            levels.editor_request_end_play();state['index']+=1
            if state['index']==len(order):finish();return
            state['phase']='wait_end'
    except Exception:finish(traceback.format_exc())

levels.editor_request_begin_play()
state['handle']=unreal.register_slate_post_tick_callback(tick)
print('100-agent benchmark scheduled')
