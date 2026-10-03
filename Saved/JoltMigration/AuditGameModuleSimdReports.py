import json,pathlib,hashlib,statistics,math,collections
import argparse
root=pathlib.Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description='Read-only full actual-NN game-module ISA report reduction; no UE/build actions.')
parser.add_argument('--report',action='append',help='Report path or stem; replaces the default two retained SSE2 reports.')
parser.add_argument('--append-report',action='append',default=[],help='Add a candidate to the default/explicit reports.')
parser.add_argument('--sse2-build',default='Saved/JoltMigration/GameSSE2PrivateBuildEvidence.json')
parser.add_argument('--avx2-build',default='Saved/JoltMigration/GameAVX2PrivateBuildEvidence.json')
parser.add_argument('--output',default='Saved/JoltMigration/GameModuleSimdComparison.json')
args=parser.parse_args()
names=(args.report or ['game_sse2_private_100_A_20260909_1557','game_sse2_private_100_B_20260909_1558'])+args.append_report
sources=[(n,True,7,8) for n in names]
def resolve_local(n):
    p=pathlib.Path(n)
    return (p if p.is_absolute() else root/p).resolve()
def resolve_report(n):
    p=pathlib.Path(n)
    return resolve_local(n if p.suffix=='.json' else 'Saved/Benchmarks/'+n+'.json')
build_paths={'SSE2_PRIVATE':resolve_local(args.sse2_build),'AVX2_PRIVATE':resolve_local(args.avx2_build)}
builds={k:json.loads(p.read_text(encoding='utf-8-sig')) for k,p in build_paths.items() if p.exists()}
output_path=resolve_local(args.output)
if not output_path.is_relative_to((root/'Saved/JoltMigration').resolve()):raise ValueError('Output must stay under Saved/JoltMigration.')

out={'schema':1,'scope':'Complete retained actual-NN reports, independently reduced without UE/build/source changes. Runs are linked to preflight sidecars and saved compiler/binary evidence; no current DLL inspection occurs after replacement. Timings are elapsed world/GT wall intervals, not summed worker CPU cycles.','runs':[]}
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
    profile_name=profile.get('profile','UNKNOWN'); avx=profile_name=='AVX2_PRIVATE'
    sidepath=root/'Saved/JoltMigration'/(path.stem+'.game-simd.cpu.json')
    side=json.loads(sidepath.read_text(encoding='utf-8-sig')) if sidepath.exists() else {}
    cpu=side.get('cpu',{})
    ck('guarded_matching_runtime_profile',profile_name in build_paths and side.get('kind')=='game_module_isa_diagnostic' and side.get('expectedGameProfile')==profile_name==profile.get('expected_profile') and profile.get('private_pch_requested') and profile.get('profile_id')==(2 if avx else 1) and resolve_local(profile.get('preflight_sidecar','MISSING'))==sidepath.resolve() and resolve_local(side.get('benchmarkReport','MISSING'))==path)
    ck('CPU_baseline_probe_full_2015_admission',side.get('accepted') and side.get('cpuProbeExitCode')==0 and cpu.get('baseline_probe') and cpu.get('supported') and cpu.get('required_instruction_mask')==cpu.get('supported_instruction_mask')==2015 and cpu.get('missing_instruction_mask')==0 and all(cpu.get(k) for k in ('popcnt','xsave','osxsave','avx_os_context')) and cpu.get('xcr0',0)&6==6)
    ck('compiler_and_Unreal_ISA_flags_match_profile',all(profile.get(k)==avx for k in ('compiler_avx2','platform_always_has_avx','platform_always_has_avx2','ue_math_uses_avx')) and profile.get('editor_build') and not profile.get('shipping_build'))
    layouts={'FVector':(24,8),'FQuat':(32,16),'FTransform':(96,16),'FMatrix':(128,16),'PersistentVectorRegister4Double':(32,16),'VectorRegister4Double':(32,32 if avx else 16)}
    ck('persistent_storage_layouts_and_expected_temporary_alignment',all(profile.get('layouts',{}).get(k)=={'size_bytes':v[0],'alignment_bytes':v[1]} for k,v in layouts.items()))
    expected_request={'count':100,'warmup':60,'samples':360,'repeats':1,'method':'NNJoltCrowd','movementOnly':True,'floorOnly':True,'workers':7,'paddingCm':40.0,'duringPhysics':True,'serialCompose':False,'pClassGameThread':True,'noLockIdleReads':True,'pauseChaos':False,'processPriority':'Normal'}
    ck('identical_explicit_requested_workload',side.get('requested')==expected_request)
    ck('native_profile_remains_SSE2',side.get('joltNativeProfile')=='SSE2' and side.get('joltNativeImportedFilename')=='ProphecyJolt_5_6_Development.dll')
    build=builds.get(profile_name)
    ck('matching_saved_build_evidence_available',build is not None and build.get('all_verified',False))
    filemap={'gameModule':'game','joltUnrealModule':'jolt_consumer','joltNative':'jolt_native','engineCoreModule':'engine_core','engineRuntimeModule':'engine','ortNative':'ort','engineExecutable':'editor_commandlet_executable'}
    ck('all_preflight_binary_hashes_match_saved_build',build is not None and all(side.get(a,{}).get('sha256','').lower()==build.get('binaries',{}).get(b,{}).get('sha256','MISSING').lower() and side.get(a,{}).get('bytes')==build.get('binaries',{}).get(b,{}).get('bytes') for a,b in filemap.items()))
    compile_rows=[z for z in (build or {}).get('compiler_inputs',[]) if z['file']!='GameAnimationSample3.Shared.rsp']
    ck('matched_private_PCH_unchanged_fp_saved_responses',bool(compile_rows) and all(z['fp_flags']==['/fp:fast'] and z['arch_flags']==(['/arch:AVX2'] if avx else []) and any('PCH.GameAnimationSample3.h' in f for f in z['pch_flags']) and not any('SharedPCH' in f for f in z['pch_flags']) for z in compile_rows))
    provenance={'runtime_game_module':profile,'sidecar':str(sidepath),'sidecar_sha256':hashlib.sha256(sidepath.read_bytes()).hexdigest() if sidepath.exists() else None,'prelaunch_binary_identities':{k:side.get(k) for k in filemap},'CPU_admission':cpu,'CPU_probe_identity':side.get('cpuProbe'),'CPU_probe_manifest_identity':side.get('cpuProbeBuildManifest'),'requested':side.get('requested'),'native_import':side.get('joltNativeImportedFilename'),'saved_build_evidence':str(build_paths.get(profile_name,'')),'saved_build_evidence_sha256':hashlib.sha256(build_paths[profile_name].read_bytes()).hexdigest() if build else None,'scope':'Pre-launch sidecar hashes bound to saved capture-time DLL hashes and loaded runtime profile; no active binary reads after replacement, continuous memory monitoring or complete ABI proof.'}

    entry={'report':str(path),'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'verified':all(checks.values()),'checks':checks,'flags_from_all_rows':{'no_lock_idle_body_reads':nolock,'worker_threads':workers,'job_concurrency':concurrency,'during_physics_group':2,'dt':d['fixed_dt'],'collision_steps':1,'warmup_frames':d['warmup_frames'],'sample_frames':d['sample_frames'],'query_tree_settings':d['query_tree_settings_at_finish']},'timing':stats,'mean_historical_jolt_step_ms':statistics.fmean(r['jolt']['last_step_ms'] for r in rows),'mean_native_step_parts_ms':parts,'max_native_partition_error_ms':partition,'mean_character_cpu_ms':phases,'phase_call_totals':calls,'counts':dict(counts),'queries':dict(qcounts),'max_errors':dict(maxima),'actual_nn':nn,'initial_nn_counters':{'steps':initial['completed_nn_steps'],'physical_samples':initial['completed_physical_samples']},'last_nn_counters':{'steps':rows[-1]['actual_nn']['completed_nn_steps'],'physical_samples':rows[-1]['actual_nn']['completed_physical_samples']},'active_body_histogram':dict(sorted(collections.Counter(r['jolt']['active_bodies'] for r in rows).items())),'placement':{'frame_starts':dict(sorted(start.items())),'frame_ends':dict(sorted(end.items())),'differing_frame_endpoints':migrated,'refresh_entry_by_cpu':dict(sorted(refresh.items())),'refresh_calls_by_efficiency_class':dict(classes),'max_refresh_phase_partition_error_ms':phase_error,'max_refresh_call_partition_error':call_error,'control':control,'initial_policy':env['initial_policy'],'final_policy':env['final_policy'],'scope':'Entry/exit observations, not continuous residency, clocks, thermals or actual worker utilization.'},'lifecycle':{'synthetic_callback_mutation':m['completed_pose_callback_invalidation'],'removed_during_bone_finalization':m['removed_during_bone_finalization'],'removed_handles_rejected':m['removed_handles_rejected'],'survivor_handles_preserved':m['survivor_handles_preserved'],'survivors_validated':len(s),'after_one_removed':m['after_one_removed'],'after_survivor_step':m['after_survivor_step'],'late_admission_cancellation':late,'after_disable':m['after_disable'],'stale_handles_rejected':m['stale_handles_rejected'],'returned_kinematic':m['returned_kinematic']},'coverage_limits':{'contact_scope':m['contact_scope'],'angular_policy':h['angular_policy'],'render_scope':m['render_scope'],'natural_motion_edge_rays':m['disjoint_previous_query_bounds_rays'],'external_post_endphysics_control_required':m['external_post_endphysics_control_required'],'external_control_test':m['external_post_endphysics_control_test'],'next_frame_admission_exercised':late['next_frame_admission_exercised'],'next_frame_cancellation_drain_exercised':late['next_frame_cancellation_drain_exercised']}}
    entry['game_ISA_provenance']=provenance
    entry['engine_ISPC_evidence']=ispc
    entry['paused_chaos_evidence']=pause_evidence
    entry['nn_increment_histogram']={str(k):v for k,v in nn_increment_hist.items()}
    entry['native_capacity']={k:h[k] for k in ('max_bodies','max_body_pairs','max_contact_constraints','temporary_allocator_bytes','jolt_commit')}
    entry['capsule_policy']=capsule
    out['runs'].append(entry)
    print(name, 'verified',entry['verified'],'failed',[k for k,v in checks.items() if not v], 'world',stats,'parts',parts,'active',entry['active_body_histogram'],'fallbacks',qcounts['ignored_own_capsule_fallbacks'],qcounts['center_ray_capsule_filters'])
    del d,x,rows,m,nn,initial,h,env,control,s

out['all_verified']=all(r['verified'] for r in out['runs'])
out['pairwise_comparisons']=[]
for a in range(len(out['runs'])):
    for b in range(a+1,len(out['runs'])):
        x=out['runs'][a];y=out['runs'][b];xp=x['game_ISA_provenance'];yp=y['game_ISA_provenance']
        same_external=all((xp['prelaunch_binary_identities'].get(k) or {}).get('sha256','MISSING_X').lower()==(yp['prelaunch_binary_identities'].get(k) or {}).get('sha256','MISSING_Y').lower() for k in ('joltUnrealModule','joltNative','engineCoreModule','engineRuntimeModule','ortNative','engineExecutable'))
        xb=builds.get(xp['runtime_game_module'].get('profile'));yb=builds.get(yp['runtime_game_module'].get('profile'))
        def source_map(build):
            return {str(pathlib.Path(z['path']).relative_to(root)):z['sha256'] for z in build.get('source_tree_hashes',[])}
        source_equal=xb is not None and yb is not None and bool(source_map(xb)) and source_map(xb)==source_map(yb)
        comparison={'from':x['report'],'to':y['report'],'from_profile':xp['runtime_game_module'].get('profile'),'to_profile':yp['runtime_game_module'].get('profile'),'same_external_DLL_hashes':same_external,'same_game_source_hashes':source_equal,'same_requested_controls':xp['requested']==yp['requested'],'world_mean_delta_ms':y['timing']['mean_ms']-x['timing']['mean_ms'],'world_mean_percent':100*(y['timing']['mean_ms']/x['timing']['mean_ms']-1),'world_reported_median_delta_ms':y['timing']['median_ms_upper_order_statistic']-x['timing']['median_ms_upper_order_statistic'],'world_conventional_median_delta_ms':y['timing']['conventional_median_ms']-x['timing']['conventional_median_ms'],'world_p95_delta_ms':y['timing']['p95_ms_order_index342']-x['timing']['p95_ms_order_index342'],'native_parts_delta_ms':{k:y['mean_native_step_parts_ms'][k]-x['mean_native_step_parts_ms'][k] for k in x['mean_native_step_parts_ms']},'character_phase_delta_ms':{k:y['mean_character_cpu_ms'][k]-x['mean_character_cpu_ms'][k] for k in x['mean_character_cpu_ms']}}
        comparison['comparison_controls_verified']=same_external and source_equal and comparison['same_requested_controls']
        out['pairwise_comparisons'].append(comparison)
        out['all_verified'] &= comparison['comparison_controls_verified']
out['profile_groups']={}
for profile in sorted({r['game_ISA_provenance']['runtime_game_module'].get('profile','UNKNOWN') for r in out['runs']}):
    group=[r for r in out['runs'] if r['game_ISA_provenance']['runtime_game_module'].get('profile','UNKNOWN')==profile]
    out['profile_groups'][profile]={'runs':len(group),'world_run_mean_ms':[r['timing']['mean_ms'] for r in group],'unweighted_mean_of_run_means_ms':statistics.fmean(r['timing']['mean_ms'] for r in group),'scope':'All complete runs remain separately reported; aggregation does not prove causal speedup.'}
out['scope']+=' Storage checks cover reported Unreal math types only; temporary SIMD alignment differs intentionally. Native/Core/Engine/ORT binary hashes and game source hashes must match across profiles.'
output_path.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print('SAVED',output_path,'all_verified',out['all_verified'])
print('GROUPS',json.dumps(out['profile_groups']))
raise SystemExit(0 if out['all_verified'] else 1)
