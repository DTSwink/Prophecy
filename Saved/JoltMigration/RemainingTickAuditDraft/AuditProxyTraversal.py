"""Read-only strict historical/native-proxy candidate report comparison. No UE/build actions."""
import json, pathlib, hashlib, statistics, math, collections, argparse, re
root=pathlib.Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline', default='nn_jolt_feedback_original_100_20260909_1641')
parser.add_argument('--candidate', action='append', default=None)
parser.add_argument('--baseline-before', default='Saved/JoltMigration/FeedbackBatchBinaryCapture-20260909-1641.json')
parser.add_argument('--baseline-after', default='Saved/JoltMigration/FeedbackBatchBinaryAfter-20260909-1641.json')
parser.add_argument('--candidate-before', default='Saved/JoltMigration/ProxyTraversalBinaryCapture-20260909-2019.json')
parser.add_argument('--candidate-after', default='Saved/JoltMigration/ProxyTraversalBinaryAfter-20260909-2020.json')
parser.add_argument('--query-tests', default='Saved/JoltMigration/Foundation-20260909-201658-412/index.json')
parser.add_argument('--output', default='Saved/JoltMigration/RemainingTickAuditDraft/ProxyTraversalComparison.json')
args=parser.parse_args()
def resolve_local(value):
    path=pathlib.Path(value)
    return (path if path.is_absolute() else root/path).resolve()
def resolve_report(value):
    path=pathlib.Path(value)
    return resolve_local(value if path.suffix=='.json' else 'Saved/Benchmarks/'+value+'.json')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
binary_keys=('gameModule','joltUnrealModule','joltNative','engineCoreModule','engineRuntimeModule','ortNative','engineExecutable')
def audit_capture(before_value, after_value, required_reports, kind):
    bp,ap=resolve_local(before_value),resolve_local(after_value); before,after=read(bp),read(ap)
    checks={'kind_and_DEFAULT_profile':before.get('kind')==kind and before.get('expectedGameProfile')=='DEFAULT'}
    if 'files' in after:
        items={v['key']:v for v in after['files']}
        checks['matching_capture_reference']=after.get('capture')==bp.name and after.get('allMatched') is True and len(after['files'])==7
        pairs={k:(items.get(k,{}).get('sha256'),items.get(k,{}).get('matches')) for k in binary_keys}
    else:
        items={v['name']:v for v in after['checks']}
        checks['matching_capture_reference']=resolve_local(after.get('before',''))==bp and after.get('success') is True and len(after['checks'])==7
        pairs={k:(items.get(k,{}).get('after'),items.get(k,{}).get('matches')) for k in binary_keys}
        checks['after_recorded_before_hashes_match_capture']=all(str(items.get(k,{}).get('before','')).lower()==str(before.get(k,{}).get('sha256','')).lower() for k in binary_keys)
    checks['exact_seven_keys']=set(items)==set(binary_keys)
    checks['required_reports_captured_as_Original']=all(sum(resolve_report(v['path'])==resolve_report(report) and v.get('feedbackMode')=='Original' for v in before['reports'])==1 for report in required_reports)
    bchecks={}
    for k in binary_keys:
        h=str(before.get(k,{}).get('sha256','')).lower(); other,matched=pairs[k]
        bchecks[k]=bool(re.fullmatch('[0-9a-f]{64}',h)) and h==str(other).lower() and matched is True and before[k]['bytes']>0
    checks['seven_boundary_hashes_match']=all(bchecks.values())
    checks['native_SSE2_DLL_filename']=pathlib.Path(before['joltNative']['path']).name=='ProphecyJolt_5_6_Development.dll'
    return {'before_file':str(bp),'before_sha256':sha(bp),'after_file':str(ap),'after_sha256':sha(ap),'before':before,'after':after,'checks':checks,'binary_checks':bchecks,'verified':all(checks.values())}
candidates=args.candidate or ['nn_jolt_proxy_traversal_100_20260909_2019']
old=audit_capture(args.baseline_before,args.baseline_after,[args.baseline],'feedback_batch_same_binary_comparison')
new=audit_capture(args.candidate_before,args.candidate_after,candidates,'native_proxy_traversal_candidate')
cross={k:old['before'][k]['sha256'].lower()==new['before'][k]['sha256'].lower() for k in binary_keys}
capture_checks={'historical_capture_verified':old['verified'],'candidate_capture_verified':new['verified'],'only_game_module_binary_changed':not cross['gameModule'] and all(v for k,v in cross.items() if k!='gameModule')}
mode_ids={'Original':0,'PreparedSerial':1,'PreparedParallel':2}
sources=[(args.baseline,True,7,8,'Original',2,'historical_original')]+[(v,True,7,8,'Original',1,'native_proxy_candidate_'+str(i+1)) for i,v in enumerate(candidates)]
output_path=resolve_local(args.output)
if not output_path.is_relative_to((root/'Saved/JoltMigration').resolve()): raise ValueError('Output must stay under Saved/JoltMigration.')
out={'prior_strict_auditor_sha256':'cd516167f590e068bfaf65152b0001fce5d146b55cbbd9be64bbb146e656d231','schema':1,'scope':'All rows of historical Original and later native-proxy candidate runs. These have different game DLLs and are not a same-binary or time-matched A/B. World times are NullRHI elapsed wall intervals, not summed CPU work or rendered FPS.','binary_provenance':{'historical':old,'candidate':new,'cross_build_same_hash':cross,'checks':capture_checks,'scope':'Before/after boundary file identity checks; not continuous loaded-memory proof. Known source changes include native-proxy traversal, strengthened query test and the two runtime Blueprint-class-flag compile fixes.'},'runs':[]}
for name, nolock, workers, concurrency, expected_mode_name, expected_preupdates, label in sources:
    expected_mode = mode_ids[expected_mode_name]
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

    profile=d.get('game_module_build_profile', {})
    ck('ordinary_DEFAULT_profile_no_private_PCH_or_AVX', profile.get('profile') == 'DEFAULT' and profile.get('profile_id') == 0 and not profile.get('private_pch_requested') and not profile.get('expected_profile') and not profile.get('preflight_sidecar') and all(profile.get(k) is False for k in ('compiler_avx2','platform_always_has_avx','platform_always_has_avx2','ue_math_uses_avx','ue_math_uses_fma3_intrinsics')) and profile.get('editor_build') and not profile.get('shipping_build'))
    layouts={'FVector':(24,8),'FQuat':(32,16),'FTransform':(96,16),'FMatrix':(128,16),'PersistentVectorRegister4Double':(32,16),'VectorRegister4Double':(32,16)}
    ck('reported_DEFAULT_math_storage_layouts', all(profile.get('layouts',{}).get(k)=={'size_bytes':v[0],'alignment_bytes':v[1]} for k,v in layouts.items()))
    ck('comparison_binary_capture_verified', all(capture_checks.values()))
    ck('same_padding40_no_pause_control', d['query_tree_settings_at_finish']['padding_override_requested'] and d['query_tree_settings_at_finish']['runtime_cvars']['p.aabbtree.DynamicTreeBoundingBoxPadding']==40 and not diag['requested'])
    ck('fresh_60hz_endpoint_expansions_preserved', all(r['character_cpu_calls']['target_endpoint_expand']==100 for r in rows))
    fixed_publication_phases = ('completed_pose_serial', 'anim_buffer', 'parallel_wait', 'anim_tick', 'refresh_bones', 'query_update', 'pose_proxy_preevaluate', 'pose_proxy_evaluate', 'pose_proxy_postevaluate_base', 'pose_finalize_after_query')
    ck('every_frame_exact_expected_PreUpdate_count', all(r['character_cpu_calls']['pose_proxy_preupdate']==expected_preupdates*100 for r in rows))
    ck('every_frame_all_required_publication_evaluation_query_finalization_calls', all(all(r['character_cpu_calls'][k]==100 for k in fixed_publication_phases) and r['character_cpu_calls']['pose_publication_validation']==600 for r in rows))

    ck('all_numeric_timing_samples_finite_nonnegative', all(math.isfinite(v) and v>=0 for v in world) and all(math.isfinite(v) and v>=0 for r in rows for obj in (r['character_cpu_ms'],r['jolt']['step_parts_ms']) for v in obj.values()))
    ck('initial_and_summary_feedback_mode', initial['physical_feedback_mode']==nn['physical_feedback_mode']==expected_mode)
    prepared = expected_mode != 0
    ck('prepared_summary_exact_180_joins_18000_items_or_Original_zero', nn['prepared_physical_samples']==(18000 if prepared else 0) and nn['prepared_physical_batches']==(180 if prepared else 0))
    ck('initial_prepared_counters_match_actual_previous_work', initial['prepared_physical_samples']==(initial['completed_physical_samples'] if prepared else 0) and initial['prepared_physical_batches']==(initial['completed_nn_steps'] if prepared else 0))
    previous_feedback=initial
    feedback_rows=[]
    feedback_valid=True
    feedback_calls_valid=True
    feedback_enclosure_error=0.
    delta_hist=collections.Counter()
    selected_phases=('manager_tick_total','manager_visual_roots','manager_physical_resample','physical_sample_read','physical_raw_encode','physical_feedback_prepare','physical_feedback_batch_wall','agent_tick_total','coordinator_total')
    timer_keys=('build_seconds','inference_seconds','output_seconds','store_seconds')
    for i,r in enumerate(rows):
        current=r['actual_nn']
        deltas={k:current[k]-previous_feedback[k] for k in ('completed_nn_steps','completed_physical_samples','prepared_physical_samples','prepared_physical_batches')}
        timer_deltas={k:1000*(current[k]-previous_feedback[k]) for k in timer_keys}
        step=deltas['completed_nn_steps']
        expected_calls={'manager_physical_resample':step,'physical_sample_read':100*step,'physical_raw_encode':0 if prepared else 200*step,'physical_feedback_prepare':100*step if prepared else 0,'physical_feedback_batch_wall':step if prepared else 0,'manager_pose_publish':100*step}
        actual_calls={k:r['character_cpu_calls'][k] for k in expected_calls}
        mode_ok=current['physical_feedback_mode']==expected_mode
        counters_ok=step in (0,1) and deltas['completed_physical_samples']==100*step and deltas['prepared_physical_samples']==(100*step if prepared else 0) and deltas['prepared_physical_batches']==(step if prepared else 0)
        timers_ok=all(math.isfinite(v) and v>=-1e-9 for v in timer_deltas.values()) and (step==1 or all(abs(v)<1e-9 for v in timer_deltas.values()))
        calls_ok=actual_calls==expected_calls
        feedback_valid &= mode_ok and counters_ok and timers_ok
        feedback_calls_valid &= calls_ok
        delta_hist[(step,deltas['completed_physical_samples'],deltas['prepared_physical_samples'],deltas['prepared_physical_batches'])]+=1
        phase_ms={k:r['character_cpu_ms'][k] for k in selected_phases}
        enclosed=phase_ms['physical_sample_read']+phase_ms['physical_feedback_prepare']+phase_ms['physical_feedback_batch_wall']+phase_ms['physical_raw_encode']
        feedback_enclosure_error=max(feedback_enclosure_error,enclosed-phase_ms['manager_physical_resample'])
        feedback_rows.append({'sample_frame':i,'feedback_mode':current['physical_feedback_mode'],'counter_deltas':deltas,'nn_timer_delta_ms':timer_deltas,'actual_phase_calls':actual_calls,'mode_counters_timers_valid':bool(mode_ok and counters_ok and timers_ok),'phase_calls_match_NN_step':calls_ok,'world_ms':world[i],'phase_ms':phase_ms})
        previous_feedback=current
    ck('all_360_feedback_mode_counter_and_NN_timer_correlations', feedback_valid)
    ck('all_360_preparation_join_sampling_raw_scope_calls_match_NN_delta', feedback_calls_valid)
    ck('feedback_scopes_remain_inside_inclusive_resample_wall', feedback_enclosure_error<1e-6)
    ck('final_prepared_counters_minus_initial_match_summary', all(rows[-1]['actual_nn'][k]-initial[k]==nn[k] for k in ('prepared_physical_samples','prepared_physical_batches')))
    nn_summary_map={'build_seconds':'mean_nn_build_ms_per_world_frame','inference_seconds':'mean_nn_inference_ms_per_world_frame','output_seconds':'mean_nn_output_ms_per_world_frame','store_seconds':'mean_nn_store_ms_per_world_frame'}
    ck('NN_timer_deltas_match_all_summary_means', all(abs(statistics.fmean(r['nn_timer_delta_ms'][k] for r in feedback_rows)-nn[v])<1e-9 for k,v in nn_summary_map.items()))
    feedback_groups={}
    for step in (0,1):
        chosen=[v for v in feedback_rows if v['counter_deltas']['completed_nn_steps']==step]
        feedback_groups['NN_step' if step else 'interpolation_only']={'frames':len(chosen),'world_mean_ms':statistics.fmean(v['world_ms'] for v in chosen),'world_median_ms':statistics.median(v['world_ms'] for v in chosen),'phase_mean_ms':{k:statistics.fmean(v['phase_ms'][k] for v in chosen) for k in selected_phases},'nn_timer_mean_ms':{k:statistics.fmean(v['nn_timer_delta_ms'][k] for v in chosen) for k in timer_keys}}
    workload={'count':d['count'],'warmup':d['warmup_frames'],'samples':d['sample_frames'],'fixed_dt':d['fixed_dt'],'mode':x['mode'],'fixture':x['fixture'],'movement_only':d['movement_only'],'nullrhi':d['nullrhi'],'no_lock':nolock,'workers':workers,'concurrency':concurrency,'compose_batch':True,'during_physics':2,'query_tree_settings':d['query_tree_settings_at_finish'],'pause_requested':diag['requested'],'pclass_control_applied_restored':checks['gt_control_applied_restored'],'nn_scope':{k:v for k,v in ns.items() if k!='root_capsule_policies'},'capsule_policy':capsule,'game_profile':profile,'ispc':ispc}
    entry={'report':str(path),'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'verified':all(checks.values()),'checks':checks,'flags_from_all_rows':{'no_lock_idle_body_reads':nolock,'worker_threads':workers,'job_concurrency':concurrency,'during_physics_group':2,'dt':d['fixed_dt'],'collision_steps':1,'warmup_frames':d['warmup_frames'],'sample_frames':d['sample_frames'],'query_tree_settings':d['query_tree_settings_at_finish']},'timing':stats,'mean_historical_jolt_step_ms':statistics.fmean(r['jolt']['last_step_ms'] for r in rows),'mean_native_step_parts_ms':parts,'max_native_partition_error_ms':partition,'mean_character_cpu_ms':phases,'phase_call_totals':calls,'counts':dict(counts),'queries':dict(qcounts),'max_errors':dict(maxima),'actual_nn':nn,'initial_nn_counters':{'steps':initial['completed_nn_steps'],'physical_samples':initial['completed_physical_samples']},'last_nn_counters':{'steps':rows[-1]['actual_nn']['completed_nn_steps'],'physical_samples':rows[-1]['actual_nn']['completed_physical_samples']},'active_body_histogram':dict(sorted(collections.Counter(r['jolt']['active_bodies'] for r in rows).items())),'placement':{'frame_starts':dict(sorted(start.items())),'frame_ends':dict(sorted(end.items())),'differing_frame_endpoints':migrated,'refresh_entry_by_cpu':dict(sorted(refresh.items())),'refresh_calls_by_efficiency_class':dict(classes),'max_refresh_phase_partition_error_ms':phase_error,'max_refresh_call_partition_error':call_error,'control':control,'initial_policy':env['initial_policy'],'final_policy':env['final_policy'],'scope':'Entry/exit observations, not continuous residency, clocks, thermals or actual worker utilization.'},'lifecycle':{'synthetic_callback_mutation':m['completed_pose_callback_invalidation'],'removed_during_bone_finalization':m['removed_during_bone_finalization'],'removed_handles_rejected':m['removed_handles_rejected'],'survivor_handles_preserved':m['survivor_handles_preserved'],'survivors_validated':len(s),'after_one_removed':m['after_one_removed'],'after_survivor_step':m['after_survivor_step'],'late_admission_cancellation':late,'after_disable':m['after_disable'],'stale_handles_rejected':m['stale_handles_rejected'],'returned_kinematic':m['returned_kinematic']},'coverage_limits':{'contact_scope':m['contact_scope'],'angular_policy':h['angular_policy'],'render_scope':m['render_scope'],'natural_motion_edge_rays':m['disjoint_previous_query_bounds_rays'],'external_post_endphysics_control_required':m['external_post_endphysics_control_required'],'external_control_test':m['external_post_endphysics_control_test'],'next_frame_admission_exercised':late['next_frame_admission_exercised'],'next_frame_cancellation_drain_exercised':late['next_frame_cancellation_drain_exercised']}}
    entry['engine_ISPC_evidence']=ispc
    entry['paused_chaos_evidence']=pause_evidence
    entry['nn_increment_histogram']={str(k):v for k,v in nn_increment_hist.items()}
    entry['native_capacity']={k:h[k] for k in ('max_bodies','max_body_pairs','max_contact_constraints','temporary_allocator_bytes','jolt_commit')}
    entry['capsule_policy']=capsule

    entry['feedback_mode_name']=expected_mode_name
    entry['feedback_mode_id']=expected_mode
    entry['runtime_game_profile']=profile
    entry['matched_workload']=workload
    entry['feedback']={'mode_name':expected_mode_name,'mode_id':expected_mode,'rows':feedback_rows,'delta_histogram':[{'NN_steps':k[0],'physical_samples':k[1],'prepared_samples':k[2],'prepared_batches':k[3],'frames':v} for k,v in sorted(delta_hist.items())],'frame_groups':feedback_groups,'max_scope_enclosure_error_ms':feedback_enclosure_error,'initial_counters':{k:initial[k] for k in ('physical_feedback_mode','completed_nn_steps','completed_physical_samples','prepared_physical_samples','prepared_physical_batches')},'final_counters':{k:rows[-1]['actual_nn'][k] for k in ('physical_feedback_mode','completed_nn_steps','completed_physical_samples','prepared_physical_samples','prepared_physical_batches')},'profiling_scope':'Prepared modes move raw encoding into joined batch wall, so raw-encode phase zero is expected and does not mean work was removed. Preparation, all kernel invocations/output writes, and serial commits finish before manager resampling returns. Scheduler cleanup may outlive ParallelFor. Parent and child phase totals overlap; do not sum them as independent costs.'}
    entry['residual_world_outside_resample_ms']=stats['mean_ms']-phases['manager_physical_resample']
    entry['top_level_world_decomposition_ms']={k:phases[k] for k in ('manager_tick_total','agent_tick_total','coordinator_total')}
    entry['top_level_world_decomposition_ms']['other_world_interval']=stats['mean_ms']-sum(entry['top_level_world_decomposition_ms'].values())
    entry['run_label']=label
    entry['expected_preupdates_per_publication']=expected_preupdates
    out['runs'].append(entry)
    print(label,'verified',entry['verified'],'failed',[k for k,v in checks.items() if not v],'world',stats,'feedback_ms',{k:phases[k] for k in ('manager_physical_resample','physical_sample_read','physical_raw_encode','physical_feedback_prepare','physical_feedback_batch_wall')})
    del d,x,rows,m,nn,initial,h,env,control,s


out['all_verified']=all(capture_checks.values()) and all(r['verified'] for r in out['runs'])
base=out['runs'][0]; out['comparisons']=[]
for candidate in out['runs'][1:]:
    same=base['matched_workload']==candidate['matched_workload']
    phase_delta={k:candidate['mean_character_cpu_ms'][k]-base['mean_character_cpu_ms'][k] for k in base['mean_character_cpu_ms']}
    world_delta=candidate['timing']['mean_ms']-base['timing']['mean_ms']
    out['comparisons'].append({'from':base['run_label'],'to':candidate['run_label'],'recorded_workload_matches':same,'same_game_binary':False,'world_mean_delta_ms':world_delta,'reported_median_delta_ms':candidate['timing']['median_ms_upper_order_statistic']-base['timing']['median_ms_upper_order_statistic'],'p95_delta_ms':candidate['timing']['p95_ms_order_index342']-base['timing']['p95_ms_order_index342'],'character_phase_delta_ms':phase_delta,'world_remainder_outside_Refresh_delta_ms':world_delta-phase_delta['refresh_bones'],'top_level_world_phase_delta_ms':{k:candidate['top_level_world_decomposition_ms'][k]-base['top_level_world_decomposition_ms'][k] for k in base['top_level_world_decomposition_ms']},'NN_timer_delta_ms_per_world_frame':{k:candidate['actual_nn'][k]-base['actual_nn'][k] for k in ('mean_nn_build_ms_per_world_frame','mean_nn_inference_ms_per_world_frame','mean_nn_output_ms_per_world_frame','mean_nn_store_ms_per_world_frame')},'preupdate_calls':{'before':base['phase_call_totals']['pose_proxy_preupdate'],'after':candidate['phase_call_totals']['pose_proxy_preupdate']},'interpretation':'The missing graph traversal produced an observed duplicate update. Runtime counters verify its removal with required evaluation/query/finalization retained. Phase and world timing differences across these historical/current runs are observations, not isolated causal performance gains.'})
    out['all_verified'] &= same
suite_path=resolve_local(args.query_tests); suite=read(suite_path); tests=suite['tests']
valid=suite['succeeded']==len(tests)==5 and all(suite[k]==0 for k in ('succeededWithWarnings','failed','notRun','inProcess')) and all(t['state']=='Success' and t.get('warnings',0)==0 and t.get('errors',0)==0 for t in tests)
chosen=[t for t in tests if t['testDisplayName']=='ImmediateFinalizeTraceAndScaleCache']
messages=[]
if len(chosen)==1:
    for e in chosen[0].get('entries',[]):
        event=e.get('event',{})
        if 'message' in event: messages.append(event['message'])
finalized=[int(re.match(r'Finalization (\d+):',msg).group(1)) for msg in messages if re.match(r'Finalization (\d+):',msg)]
valid &= finalized==[1,2,3,4,5]
out['current_query_regression']={'file':str(suite_path),'sha256':sha(suite_path),'verified':bool(valid),'succeeded':suite['succeeded'],'tests':[{'name':t['testDisplayName'],'state':t['state']} for t in tests],'logged_finalizations':finalized,'scope':'All five current query tests pass; the strengthened native traversal test exercises 5 publications including clear/reinitialization/reused revision and all 88 bones. Root performed build and test execution; this auditor reads their exported results.'}
out['all_verified'] &= bool(valid)
out['conclusion_scope']='All full runtime workload and lifetime gates independently audited; no sub-10ms, Shipping, renderer, denser-contact or matched-timing claim. Six unchanged external binaries and separately stable game DLL boundaries are verified.'
output_path.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print('SAVED',output_path,'all_verified',out['all_verified'])
raise SystemExit(0 if out['all_verified'] else 1)
