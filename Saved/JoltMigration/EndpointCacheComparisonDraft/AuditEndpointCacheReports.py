import json,pathlib,hashlib,statistics,math,collections,re,datetime,argparse
root=pathlib.Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description='Read-only complete-row endpoint-cache A/B audit; no UE/build/current binary reads.')
parser.add_argument('--capture',default='Saved/JoltMigration/EndpointCacheBinaryCapture-20260909-1630.json')
parser.add_argument('--after',default='Saved/JoltMigration/EndpointCacheBinaryAfter-20260909-1632.json')
parser.add_argument('--output',default='Saved/JoltMigration/EndpointCacheComparisonDraft/EndpointCacheComparison.json')
args=parser.parse_args()
def resolve_local(n):
    p=pathlib.Path(n)
    return (p if p.is_absolute() else root/p).resolve()
def resolve_report(n):return resolve_local(n)
capture_path=resolve_local(args.capture); after_path=resolve_local(args.after)
capture=json.loads(capture_path.read_text(encoding='utf-8-sig')); after=json.loads(after_path.read_text(encoding='utf-8-sig'))
output_path=resolve_local(args.output)
if not output_path.is_relative_to((root/'Saved/JoltMigration').resolve()):raise ValueError('Output must stay under Saved/JoltMigration.')
binary_names={'gameModule':'UnrealEditor-GameAnimationSample3.dll','joltUnrealModule':'UnrealEditor-ProphecyJolt.dll','joltNative':'ProphecyJolt_5_6_Development.dll','engineCoreModule':'UnrealEditor-Core.dll','engineRuntimeModule':'UnrealEditor-Engine.dll','ortNative':'onnxruntime.dll','engineExecutable':'UnrealEditor-Cmd.exe'}
after_rows=after.get('files',[])
after_by_key={z.get('key'):z for z in after_rows}
capture_checks={
    'typed_DEFAULT_pair_capture':capture.get('kind')=='endpoint_cache_same_binary_comparison' and capture.get('expectedGameProfile')=='DEFAULT',
    'exactly_two_distinct_report_paths_and_both_controls':len(capture.get('reports',[]))==2 and len({str(resolve_report(z['path'])) for z in capture.get('reports',[])})==2 and sorted(z['noEndpointCache'] for z in capture.get('reports',[]))==[False,True],
    'all_seven_positive_binary_identities':all(isinstance(capture.get(k,{}).get('bytes'),int) and capture[k]['bytes']>0 and re.fullmatch('[0-9a-fA-F]{64}',capture[k].get('sha256','')) and pathlib.Path(capture[k].get('path','')).is_absolute() and pathlib.Path(capture[k]['path']).name==v for k,v in binary_names.items()),
    'after_binds_capture_and_timestamp':after.get('capture')==capture_path.name and datetime.datetime.fromisoformat(after['verifiedUtc'].replace('Z','+00:00'))>=datetime.datetime.fromisoformat(capture['capturedUtc'].replace('Z','+00:00')),
    'exactly_seven_distinct_after_keys':len(after_rows)==len(after_by_key)==7 and set(after_by_key)==set(binary_names),
    'all_seven_after_hashes_match':after.get('allMatched') is True and all(after_by_key.get(k,{}).get('matches') is True and after_by_key[k].get('sha256','').lower()==capture[k]['sha256'].lower() for k in binary_names),
}
sources=[(z['path'],True,7,8) for z in capture['reports']]
expected_controls={str(resolve_report(z['path'])):z['noEndpointCache'] for z in capture['reports']}
capture_evidence={'before_path':str(capture_path),'before_sha256':hashlib.sha256(capture_path.read_bytes()).hexdigest(),'after_path':str(after_path),'after_sha256':hashlib.sha256(after_path.read_bytes()).hexdigest(),'capture_checks':capture_checks,'before':capture,'after':after,'scope':'Saved before/after file hashes and operator attestation cover this pair. The auditor does not inspect replacement DLLs, monitor process memory, or prove complete ABI/source identity continuously.'}
out={'schema':1,'scope':'Complete retained DEFAULT same-binary endpoint-cache comparison. All 360 rows per report are checked; no UE/build/current DLL reads. Timings are elapsed world/GT wall intervals, not summed worker CPU cycles.','binary_capture':capture_evidence,'runs':[]}
for name,nolock,workers,concurrency in sources:
    path=resolve_report(name)
    with path.open(encoding='utf-8-sig') as f: d=json.load(f)
    x=d['passes'][0]; rows=x['multi_jolt_frames']; m=x['multi_jolt_validation']; nn=x['actual_nn_validation']; initial=x['before']['actual_nn_initial']; h=x['before']['multi_jolt_handoff']; env=d['processor_environment']; control=d['game_thread_processor_control']
    checks={}
    def ck(k,v): checks[k]=bool(v)
    ck('no_report_error_and_one_pass',not d['error'] and len(d['passes'])==1 and m['success'] and nn['success'])
    ck('100agents_60warmup_360samples',d['count']==100 and d['warmup_frames']==60 and d['sample_frames']==x['samples']==len(rows)==len(x['world_ms'])==360)
    ck('real_nn_workload_mode',x['mode']=='NNJoltCrowd' and x['fixture']=='floor_gravity' and d['movement_only'] and d['nullrhi'] and d['fixed_dt']==1/60 and not d['substepping'] and not d['async_physics'])
    ck('same_full_captured_rigs',len(h['source_captures'])==100 and all(a['bodies']==22 and a['joints']==21 and a['disabled_pairs']==47 for a in h['source_captures']))
    ck('180actual_nn_steps_and_18000_feedback',nn['completed_nn_steps']==180 and nn['completed_physical_samples']==18000 and rows[-1]['actual_nn']['completed_nn_steps']-initial['completed_nn_steps']==180 and rows[-1]['actual_nn']['completed_physical_samples']-initial['completed_physical_samples']==18000)
    ck('all_models_cpu_batch100_no_failed_feedback',all(all(r['actual_nn'][k]=='NNERuntimeORTCpu' for k in ('run_runtime','walk_runtime','upper_runtime')) and all(r['actual_nn'][k]==100 for k in ('run_batch_size','walk_batch_size','upper_batch_size')) and r['actual_nn']['foot_roll_steps']==4 and r['actual_nn']['failed_physical_samples']==0 for r in rows))
    ck('all_recorded_flags_match',all((r['jolt']['no_lock_idle_body_reads'],r['jolt']['worker_threads'],r['jolt']['job_concurrency'])==(nolock,workers,concurrency) for r in rows))
    ck('all360_resource_and_owner_counts',all(r['success'] and r['jolt']['initialized'] and not r['jolt']['faulted'] and r['jolt']['update_error_bits']==0 and r['jolt']['bodies']==2201 and r['jolt']['constraints']==2100 and r['coordinator_characters']==100 and r['chaos_dynamic_bodies']==0 and r['validated_dynamic_rig_bodies']==2200 and r['validated_skeleton_bones']==8800 for r in rows))
    ck('one_matching_step_and_revision_per_frame',all(r['sample_frame']==i and r['jolt']['completed_steps']==r['automatic_step_count']==i+1 and r['completed_revision']==i+2 and r['automatic_step_engine_frame']==r['validation_engine_frame'] for i,r in enumerate(rows)))
    ck('actual_duringphysics_and_dt',all(all(r[k]==2 for k in ('automatic_tick_group','actual_automatic_tick_group','actual_automatic_end_tick_group','automatic_observed_world_tick_group')) and r['jolt']['last_collision_steps']==1 and abs(r['jolt']['last_step_seconds']-1/60)<1e-8 for r in rows))
    counts=collections.Counter(); qcounts=collections.Counter(); maxima=collections.defaultdict(float); valid_agents=True
    for i,r in enumerate(rows):
        valid_agents &= len(r['agents'])==100 and {a['agent_index'] for a in r['agents']}==set(range(100))
        for a in r['agents']:
            counts['agent_frames']+=1; counts['dynamic_body_checks']+=a['validated_dynamic_rig_bodies']; counts['skeleton_bone_checks']+=a['validated_skeleton_bones']
            valid_agents &= a['success'] and a['validated_dynamic_rig_bodies']==22 and a['validated_skeleton_bones']==88 and a['completed_revision']==i+2
            for k in ('max_feedback_render_position_cm','max_feedback_render_angle_degrees','max_feedback_render_scale_difference'): maxima[k]=max(maxima[k],a[k])
            q=a['post_endphysics_queries']; ray=q['center_ray']
            for key,value in {'query_successes':q['success'],'query_body_checks':q['validated_query_bodies'],'normal_head_visibility':q['normal_unfiltered_head_visibility_exercised'],'ignored_own_capsule_fallbacks':q['validation_only_ignored_own_capsule'],'center_ray_capsule_filters':ray['validation_only_capsule_filter'],'successful_head_rays':ray['success'],'head_identity_checks':ray['hit_bone']=='head' and ray['hit_component'].endswith(f'ProphecyAgent_{a["agent_index"]}.PhysicalMesh'),'capsule_identity_checks':q['own_root_is_capsule'] and q['own_blocking_capsule_shapes']==1,'after_end_group7_checks':q['observed_world_tick_group']==7,'center_analytic_candidates':q['center_analytic_candidates'],'center_analytically_occluded_candidates':q['center_analytically_occluded_candidates'],'natural_motion_edge_rays':q['disjoint_previous_aabb_ray']}.items(): qcounts[key]+=value
            for k in ('max_query_bone_position_cm','max_query_bone_angle_degrees','capsule_native_component_position_error_cm','capsule_native_component_angle_error_degrees'): maxima[k]=max(maxima[k],q[k])
            maxima['head_impact_error_cm']=max(maxima['head_impact_error_cm'],ray['impact_error_cm'])
    ck('all36000_agent_records_22bodies_88bones',valid_agents and counts=={'agent_frames':36000,'dynamic_body_checks':792000,'skeleton_bone_checks':3168000})
    ck('all_queries_unfiltered_no_capsule_fallbacks',all(qcounts[k]==36000 for k in ('query_successes','normal_head_visibility','successful_head_rays','head_identity_checks','capsule_identity_checks','after_end_group7_checks')) and qcounts['query_body_checks']==792000 and qcounts['ignored_own_capsule_fallbacks']==qcounts['center_ray_capsule_filters']==0)
    ck('all_pose_errors_within_gates',maxima['max_feedback_render_position_cm']<=.02 and maxima['max_feedback_render_angle_degrees']<=.02 and maxima['max_feedback_render_scale_difference']<=.0001 and maxima['max_query_bone_position_cm']<=.02 and maxima['max_query_bone_angle_degrees']<=.02)
    phases={k:statistics.fmean(r['character_cpu_ms'][k] for r in rows) for k in rows[0]['character_cpu_ms']}
    calls={k:sum(r['character_cpu_calls'][k] for r in rows) for k in rows[0]['character_cpu_calls']}
    parts={k:statistics.fmean(r['jolt']['step_parts_ms'][k] for r in rows) for k in rows[0]['jolt']['step_parts_ms']}
    partition=max(abs(r['jolt']['last_step_ms']-sum(v for k,v in r['jolt']['step_parts_ms'].items() if k!='post_update_validation')) for r in rows)
    ck('native_timer_partition',partition<1e-6)
    ck('summary_phase_means_match',all(abs(v-m['mean_native_step_parts_ms'][k])<1e-9 for k,v in parts.items()) and all(abs(v-m['mean_character_cpu_ms'][k])<1e-9 for k,v in phases.items()))
    ck('360_batches_no_serial_compose_fallback_no_synthetic_producer',calls['compose_batch_wall']==360 and calls['compose']==calls['fixture_pose_publish']==0)
    topo={(c['group'],c['logical_processor_index']):c['efficiency_class'] for c in env['cpu_sets']}
    start=collections.Counter(); end=collections.Counter(); refresh=collections.defaultdict(lambda:{'calls':0,'ms':0.,'different_exit_processor':0}); classes=collections.Counter(); migrated=0; phase_error=0.; call_error=0
    for r in rows:
        p=r['processor_provenance']; b=(p['begin']['group'],p['begin']['logical_processor_index']); e=(p['end']['group'],p['end']['logical_processor_index']); start[f'{b[0]}:{b[1]}']+=1; end[f'{e[0]}:{e[1]}']+=1; migrated+=b!=e
        for z in p['phase_entry_processors']:
            key=f'{z["group"]}:{z["logical_processor_index"]}'; a=z['refresh_bones']
            for k in ('calls','ms','different_exit_processor'): refresh[key][k]+=a[k]
            classes[str(topo[(z['group'],z['logical_processor_index'])])]+=a['calls']
        phase_error=max(phase_error,abs(sum(z['refresh_bones']['ms'] for z in p['phase_entry_processors'])-r['character_cpu_ms']['refresh_bones']))
        call_error=max(call_error,abs(sum(z['refresh_bones']['calls'] for z in p['phase_entry_processors'])-r['character_cpu_calls']['refresh_bones']))
    ck('sampled_gt_and_refresh_all_class1',all(topo[tuple(map(int,k.split(':')))]==1 for k in set(start)|set(end)) and classes=={'1':36000})
    ck('cpu_scope_partitions_no_overflow',phase_error<1e-6 and call_error==0 and all(r['processor_provenance']['overflowed_scope_samples']==0 for r in rows))
    ck('gt_control_applied_restored',control['requested'] and control['applied'] and control['restored'] and not control['restoration_pending'] and control['process_affinity_unchanged_after_apply'] and control['original_game_thread_affinity']==control['restored_game_thread_affinity']=={'group':0,'mask_hex':'0xfff'} and control['applied_game_thread_affinity']=={'group':0,'mask_hex':'0xff'} and control['original_process_mask_hex']==control['original_system_mask_hex']=='0xfff')
    ck('normal_process_priority_unchanged',all(env[k]['process_priority_class']==32 and env[k]['game_thread_priority']==1 and env[k]['process_affinity_mask_hex']=='0xfff' for k in ('initial_policy','final_policy')))
    s=m['survivors_after_explicit_step']; late=m['late_admission_cancellation']
    ck('removal_finalizer_and_survivor_handles',m['removed_during_bone_finalization'] and m['removed_handles_rejected']==22 and m['survivor_handles_preserved']==2178 and len(s)==99 and {a['agent_index'] for a in s}==set(range(99)) and all(a['success'] and a['validated_dynamic_rig_bodies']==22 and a['validated_skeleton_bones']==88 and a['completed_revision']==363 for a in s))
    ck('two_unmeasured_lifecycle_steps',m['after_one_removed']['bodies']==m['after_survivor_step']['bodies']==2179 and m['after_one_removed']['constraints']==m['after_survivor_step']['constraints']==2079 and m['after_one_removed']['completed_steps']==361 and m['after_survivor_step']['completed_steps']==362 and m['extra_unmeasured_lifecycle_steps']==2)
    ck('floor_only_after_teardown',m['after_disable']['bodies']==1 and m['after_disable']['constraints']==0 and m['after_disable']['completed_steps']==362 and m['coordinator_characters_after_disable']==m['chaos_dynamic_bodies_after_disable']==0 and m['stale_handles_rejected']==2200 and m['returned_kinematic'])
    ck('late_pending_cancellation',late['success'] and late['repeated_pending_enable_idempotent'] and late['pending_token_cleared'] and late['completion_delegate_cleared'] and late['completion_callbacks_on_cancellation']==0 and late['survivor_body_states_unchanged']==2178 and late['chaos_dynamic_bodies_while_pending']==22 and late['chaos_dynamic_bodies_after_cancellation']==0)
    ck('camera_subtrees_retained_detached',all(x[k]['movement_camera_subtrees_detached']==100 and x[k]['movement_camera_components_retained_in_detached_subtrees']==200 for k in ('before','after')))
    world=x['world_ms']; ordered=sorted(world); stats={'mean_ms':statistics.fmean(world),'median_ms_upper_order_statistic':ordered[180],'conventional_median_ms':statistics.median(world),'p95_ms_order_index342':ordered[342],'min_ms':min(world),'max_ms':max(world),'frames_over_10ms':sum(v>10 for v in world)}
    ck('world_statistics_match',abs(stats['mean_ms']-x['world_tick']['mean_ms'])<1e-9 and abs(stats['median_ms_upper_order_statistic']-x['world_tick']['median_ms'])<1e-9 and abs(stats['p95_ms_order_index342']-x['world_tick']['p95_ms'])<1e-9)

    ck('all_jolt_bodies_active_every_frame',all(r['jolt']['active_bodies']==2200 for r in rows))
    ns=x['before']['actual_nn_scope']
    ck('actual_30hz_NN_60hz_full_presentation',ns['nn_hz']==30 and ns['world_and_presentation_hz']==60 and ns['policy_bones']==25 and ns['presented_skeleton_bones']==88 and ns['dynamic_bodies_per_character']==22 and not ns['synthetic_publication_after_adoption'])
    capsule={'object_channel':21,'collision_enabled':3,'responses_by_channel':[2]+[0]*32,'radius_cm':30,'half_height_cm':86}
    ck('100_real_unchanged_floor_blocking_capsules',len(ns['root_capsule_policies'])==100 and all(v==capsule for v in ns['root_capsule_policies']))
    previous=initial['completed_nn_steps']; previous_samples=initial['completed_physical_samples']; nn_increment_hist=collections.Counter()
    for r in rows:
        n=r['actual_nn']; delta=n['completed_nn_steps']-previous; ds=n['completed_physical_samples']-previous_samples
        nn_increment_hist[delta]+=1
        previous=n['completed_nn_steps']; previous_samples=n['completed_physical_samples']
        if ds!=100*delta: nn_increment_hist['invalid_samples']+=1
    ck('180_inference_frames_180_interpolation_frames',nn_increment_hist=={0:180,1:180})
    ck('moving_roots_not_static_pose',nn['minimum_managed_root_travel_cm']>=1200 and nn['minimum_managed_root_travel_cm']<1201)
    ck('native_capacity_and_pinned_commit',h['max_bodies']==2201 and h['max_body_pairs']==17608 and h['max_contact_constraints']==35216 and h['temporary_allocator_bytes']==33554432 and h['jolt_commit']=='e77f175595e64cb44218cc9d9d56fc365ad0e36a')
    diag=d['paused_chaos_diagnostic']; paused_rows=[r.get('paused_chaos_maintenance') for r in rows]
    phase_hist=collections.Counter(); native_hist=collections.Counter(); dt_hist=collections.Counter()
    if not diag['requested']:
        ck('pause_not_requested_or_applied',diag=={'requested':False,'applied':False} and x['paused_chaos_diagnostic']==diag and all(z is None for z in paused_rows))
        pause_evidence={'requested':False,'applied':False,'detailed_chaos_maintenance_rows':0,'scope':'Normal control does not record per-frame Chaos solver maintenance packets; ordinary world physics path remains configured.'}
    else:
        ck('pause_requires_two_measured_positive_frames',diag['requested'] and diag['applied'] and diag['required_positive_delta_frames_before_pause']==2 and diag['positive_frames_remain_in_benchmark_samples'] and diag['validated_positive_delta_frames']==2 and diag['validated_zero_delta_frames']==358 and diag['validated_total_frames']==360 and diag['applied_after_solver_frame']==diag['begin_solver_frame']+2)
        checks_ok=True
        for i,z in enumerate(paused_rows):
            phase_hist[z['phase']]+=1
            native_hist[(z['components_with_native_objects'],z['unique_native_objects'],z['gt_kinematic_objects'],z['pt_all_particles'],z['gt_dynamic_or_sleeping_objects'],z['pt_dynamic_or_sleeping_particles'])]+=1
            dt_hist[z['solver_last_dt']]+=1
            checks_ok &= z['solver_frame']==z['external_packet_timestamp']==z['expected_solver_frame']==diag['begin_solver_frame']+i+1 and z['scene_completion_complete'] and z['world_should_simulate_physics'] and z['solver_max_substeps']==1 and abs(z['world_delta_seconds']-1/60)<1e-8 and z['gt_static_objects']==0
            checks_ok &= z['paused']==(i>=2) and ((i<2 and z['phase']=='measured_positive_delta_buffer_refresh' and abs(z['solver_last_dt']-1/60)<1e-8) or (i>=2 and z['phase']=='paused_maintenance' and z['solver_last_dt']==0))
        ck('all_360_Chaos_packets_order_dt_and_unchanged_objects',checks_ok and native_hist=={(203,2303,2303,2303,0,0):360} and phase_hist=={'measured_positive_delta_buffer_refresh':2,'paused_maintenance':358})
        ck('pause_restore_exact_original_at_settled_boundary',diag['restored'] and not diag['armed'] and diag['original_paused']==diag['restored_paused']==diag['after_restore']['paused']==False and diag['before_restore']['paused'] and diag['before_restore']['solver_frame']==diag['after_restore']['solver_frame']==419 and diag['after_restore']['scene_completion_complete'] and diag['after_restore']['pt_dynamic_or_sleeping_particles']==0 and diag['after_restore']['unique_native_objects']==diag['after_restore']['pt_all_particles']==2303)
        pause_evidence={'requested':True,'applied':True,'begin':diag['before'],'phase_counts':dict(phase_hist),'solver_dt_counts':{str(k):v for k,v in dt_hist.items()},'object_count_tuple_order':['components','native_objects','GT_kinematic','PT_particles','GT_dynamic_or_sleeping','PT_dynamic_or_sleeping'],'object_count_histogram':[{'counts':list(k),'frames':v} for k,v in native_hist.items()],'first_positive':paused_rows[0],'last_positive':paused_rows[1],'first_paused':paused_rows[2],'last_paused':paused_rows[-1],'applied_after_solver_frame':diag['applied_after_solver_frame'],'original_paused':diag['original_paused'],'restored_paused':diag['restored_paused'],'restored':diag['restored'],'after_restore':diag['after_restore'],'restoration_scope':diag['restoration_scope'],'required_independent_control':diag['required_independent_control']}


    ispc=d.get('engine_ispc_settings_at_finish',{})
    ck('stock_engine_ISPC_controls_remain_registered_enabled',ispc.get('engine_module_loaded') and ispc.get('compiled_support_proven_by_stock_engine_controls') and ispc.get('bone_pose_effective_enabled') and ispc.get('component_space_effective_enabled') and all(ispc.get('runtime_cvars',{}).get(k,{}).get('registered_bool') and ispc['runtime_cvars'][k].get('enabled') for k in ('a.BonePose.ISPC','a.SkinnedAsset.ISPC','a.SkeletalMesh.ISPC')))
    profile=d.get('game_module_build_profile',{})
    disabled=expected_controls[str(path)]
    ck('DEFAULT_shared_profile_no_private_ISA_request',profile.get('profile')=='DEFAULT' and profile.get('profile_id')==0 and profile.get('private_pch_requested') is False and profile.get('expected_profile')=='' and profile.get('preflight_sidecar')=='')
    ck('DEFAULT_compiler_and_Unreal_flags',all(profile.get(k) is False for k in ('compiler_avx2','platform_always_has_avx','platform_always_has_avx2','ue_math_uses_avx','ue_math_uses_fma3_intrinsics')) and profile.get('editor_build') is True and profile.get('shipping_build') is False)
    layouts={'FVector':(24,8),'FQuat':(32,16),'FTransform':(96,16),'FMatrix':(128,16),'PersistentVectorRegister4Double':(32,16),'VectorRegister4Double':(32,16)}
    ck('DEFAULT_reported_math_layouts',all(profile.get('layouts',{}).get(k)=={'size_bytes':v[0],'alignment_bytes':v[1]} for k,v in layouts.items()))
    ck('saved_seven_binary_before_after_capture_valid',all(capture_checks.values()))
    ck('loaded_Engine_path_binds_captured_Engine_DLL',resolve_local(ispc.get('engine_module_file','MISSING'))==resolve_local(capture['engineRuntimeModule']['path']))
    ck('ordinary_Chaos_unpaused_control',diag=={'requested':False,'applied':False})
    query_settings=[x['before']['query_tree_settings'],x['after']['query_tree_settings'],d['query_tree_settings_at_finish']]
    ck('query_padding40_and_settings_stable_all_boundaries',all(z==query_settings[0] and z['runtime_cvars']['p.aabbtree.DynamicTreeBoundingBoxPadding']==40 for z in query_settings))
    ck('ISPC_engine_controls_stable_all_boundaries',x['before']['engine_ispc_settings']==x['after']['engine_ispc_settings']==ispc)
    ck('endpoint_flag_binds_both_case_boundaries_and_finish',type(disabled) is bool and x['before']['physical_endpoint_cache_disabled_by_commandline'] is disabled and x['after']['physical_endpoint_cache_disabled_by_commandline'] is disabled and d['physical_endpoint_cache_disabled_by_commandline_at_finish'] is disabled)
    previous=initial['completed_nn_steps']; expansion_hist=collections.Counter(); expansion_nn_hist=collections.Counter(); expansion_rows=[]
    for i,r in enumerate(rows):
        delta=r['actual_nn']['completed_nn_steps']-previous; previous=r['actual_nn']['completed_nn_steps']
        count=r['character_cpu_calls']['target_endpoint_expand']; elapsed=r['character_cpu_ms']['target_endpoint_expand']; target_read=r['character_cpu_ms']['target_read']
        expansion_hist[count]+=1; expansion_nn_hist[(delta,count)]+=1
        expansion_rows.append({'sample_frame':i,'nn_delta':delta,'expand_calls':count,'expected_calls':100 if disabled else 100*delta,'expand_ms':elapsed,'target_read_ms':target_read})
    ck('every_expansion_count_matches_same_frame_NN_delta',all(z['nn_delta'] in (0,1) and type(z['expand_calls']) is int and z['expand_calls']==z['expected_calls'] for z in expansion_rows))
    ck('exact_expansion_histogram',expansion_hist==({100:360} if disabled else {0:180,100:180}))
    ck('endpoint_timing_is_finite_nested_and_zero_on_hit',all(math.isfinite(z['expand_ms']) and math.isfinite(z['target_read_ms']) and 0<=z['expand_ms']<=z['target_read_ms']+1e-9 and (z['expand_calls']!=0 or z['expand_ms']==0) for z in expansion_rows))
    ck('all_timing_values_finite_nonnegative',all(math.isfinite(v) and v>=0 for r in rows for v in list(r['character_cpu_ms'].values())+list(r['jolt']['step_parts_ms'].values())+[r['jolt']['last_step_ms']]) and all(math.isfinite(v) and v>=0 for v in world))
    expected_calls=36000 if disabled else 18000
    ck('all_full_target_reads_and_expected_total_expansions',calls['target_read']==36000 and calls['target_endpoint_expand']==expected_calls)
    provenance={'runtime_game_module':profile,'binary_capture_path':str(capture_path),'binary_after_path':str(after_path),'scope':capture_evidence['scope']}
    endpoints={'cache_disabled':disabled,'inference_delta_expansion_histogram':[{'nn_delta':k[0],'expand_calls':k[1],'frames':v} for k,v in sorted(expansion_nn_hist.items())],'expansion_histogram':dict(sorted(expansion_hist.items())),'total_expansions':calls['target_endpoint_expand'],'first_measured_row':expansion_rows[0],'last_measured_row':expansion_rows[-1],'all_rows':expansion_rows,'mean_target_read_minus_expansion_ms':phases['target_read']-phases['target_endpoint_expand'],'residual_scope':'Includes all other target-read work; this is not an isolated cache-comparison/copy timer. Warmup establishes the first cache entry; no first-frame exception is silently permitted.'}
    entry={'report':str(path),'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'verified':all(checks.values()),'checks':checks,'flags_from_all_rows':{'no_lock_idle_body_reads':nolock,'worker_threads':workers,'job_concurrency':concurrency,'during_physics_group':2,'dt':d['fixed_dt'],'collision_steps':1,'warmup_frames':d['warmup_frames'],'sample_frames':d['sample_frames'],'query_tree_settings':d['query_tree_settings_at_finish']},'timing':stats,'mean_historical_jolt_step_ms':statistics.fmean(r['jolt']['last_step_ms'] for r in rows),'mean_native_step_parts_ms':parts,'max_native_partition_error_ms':partition,'mean_character_cpu_ms':phases,'phase_call_totals':calls,'counts':dict(counts),'queries':dict(qcounts),'max_errors':dict(maxima),'actual_nn':nn,'initial_nn_counters':{'steps':initial['completed_nn_steps'],'physical_samples':initial['completed_physical_samples']},'last_nn_counters':{'steps':rows[-1]['actual_nn']['completed_nn_steps'],'physical_samples':rows[-1]['actual_nn']['completed_physical_samples']},'active_body_histogram':dict(sorted(collections.Counter(r['jolt']['active_bodies'] for r in rows).items())),'placement':{'frame_starts':dict(sorted(start.items())),'frame_ends':dict(sorted(end.items())),'differing_frame_endpoints':migrated,'refresh_entry_by_cpu':dict(sorted(refresh.items())),'refresh_calls_by_efficiency_class':dict(classes),'max_refresh_phase_partition_error_ms':phase_error,'max_refresh_call_partition_error':call_error,'control':control,'initial_policy':env['initial_policy'],'final_policy':env['final_policy'],'scope':'Entry/exit observations, not continuous residency, clocks, thermals or actual worker utilization.'},'lifecycle':{'synthetic_callback_mutation':m['completed_pose_callback_invalidation'],'removed_during_bone_finalization':m['removed_during_bone_finalization'],'removed_handles_rejected':m['removed_handles_rejected'],'survivor_handles_preserved':m['survivor_handles_preserved'],'survivors_validated':len(s),'after_one_removed':m['after_one_removed'],'after_survivor_step':m['after_survivor_step'],'late_admission_cancellation':late,'after_disable':m['after_disable'],'stale_handles_rejected':m['stale_handles_rejected'],'returned_kinematic':m['returned_kinematic']},'coverage_limits':{'contact_scope':m['contact_scope'],'angular_policy':h['angular_policy'],'render_scope':m['render_scope'],'natural_motion_edge_rays':m['disjoint_previous_query_bounds_rays'],'external_post_endphysics_control_required':m['external_post_endphysics_control_required'],'external_control_test':m['external_post_endphysics_control_test'],'next_frame_admission_exercised':late['next_frame_admission_exercised'],'next_frame_cancellation_drain_exercised':late['next_frame_cancellation_drain_exercised']}}
    entry['binary_provenance']=provenance
    entry['endpoint_evidence']=endpoints
    entry['engine_ISPC_evidence']=ispc
    entry['paused_chaos_evidence']=pause_evidence
    entry['nn_increment_histogram']={str(k):v for k,v in nn_increment_hist.items()}
    entry['native_capacity']={k:h[k] for k in ('max_bodies','max_body_pairs','max_contact_constraints','temporary_allocator_bytes','jolt_commit')}
    entry['capsule_policy']=capsule
    out['runs'].append(entry)
    print(name, 'verified',entry['verified'],'failed',[k for k,v in checks.items() if not v], 'world',stats,'parts',parts,'active',entry['active_body_histogram'],'fallbacks',qcounts['ignored_own_capsule_fallbacks'],qcounts['center_ray_capsule_filters'])
    del d,x,rows,m,nn,initial,h,env,control,s


out['all_verified']=all(capture_checks.values()) and all(r['verified'] for r in out['runs'])
off=next(r for r in out['runs'] if r['endpoint_evidence']['cache_disabled'])
on=next(r for r in out['runs'] if not r['endpoint_evidence']['cache_disabled'])
same_controls=off['flags_from_all_rows']==on['flags_from_all_rows'] and off['binary_provenance']['runtime_game_module']==on['binary_provenance']['runtime_game_module'] and off['engine_ISPC_evidence']==on['engine_ISPC_evidence'] and off['native_capacity']==on['native_capacity'] and off['capsule_policy']==on['capsule_policy']
out['comparison']={'from':off['report'],'to':on['report'],'direction':'cache enabled minus disabled','same_captured_seven_binaries':all(capture_checks.values()),'same_runtime_controls_except_cache':same_controls,'comparison_controls_verified':same_controls and all(capture_checks.values()),'world_mean_delta_ms':on['timing']['mean_ms']-off['timing']['mean_ms'],'world_mean_percent':100*(on['timing']['mean_ms']/off['timing']['mean_ms']-1),'world_median_delta_ms':on['timing']['median_ms_upper_order_statistic']-off['timing']['median_ms_upper_order_statistic'],'world_p95_delta_ms':on['timing']['p95_ms_order_index342']-off['timing']['p95_ms_order_index342'],'native_parts_delta_ms':{k:on['mean_native_step_parts_ms'][k]-off['mean_native_step_parts_ms'][k] for k in off['mean_native_step_parts_ms']},'character_phase_delta_ms':{k:on['mean_character_cpu_ms'][k]-off['mean_character_cpu_ms'][k] for k in off['mean_character_cpu_ms']},'target_read_residual_delta_ms':on['endpoint_evidence']['mean_target_read_minus_expansion_ms']-off['endpoint_evidence']['mean_target_read_minus_expansion_ms'],'scope':'One retained sequential A/B pair, not a confidence interval or isolation of scheduler/thermal noise. The endpoint cache halves actual expansions but its enclosing target-read phase must improve to justify adoption.'}
out['all_verified'] &= out['comparison']['comparison_controls_verified']
output_path.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print('SAVED',output_path,'all_verified',out['all_verified'])
print('COMPARISON',json.dumps(out['comparison']))
raise SystemExit(0 if out['all_verified'] else 1)
