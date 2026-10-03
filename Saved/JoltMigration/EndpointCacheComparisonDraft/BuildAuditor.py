"""Draft-only adaptation of the existing complete-row ISA auditor."""
import pathlib

here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
source = (root / 'Saved/JoltMigration/AuditGameModuleSimdReports.py').read_text(encoding='utf-8-sig')
header = r'''import json,pathlib,hashlib,statistics,math,collections,re,datetime,argparse
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
'''
body=source[source.index("out={'schema':1"):source.index("out['all_verified']=all")]
body=body.replace("'scope':'Complete retained actual-NN reports, independently reduced without UE/build/source changes. Runs are linked to preflight sidecars and saved compiler/binary evidence; no current DLL inspection occurs after replacement. Timings are elapsed world/GT wall intervals, not summed worker CPU cycles.'", "'scope':'Complete retained DEFAULT same-binary endpoint-cache comparison. All 360 rows per report are checked; no UE/build/current DLL reads. Timings are elapsed world/GT wall intervals, not summed worker CPU cycles.'")
body=body.replace("'runs':[]}","'binary_capture':capture_evidence,'runs':[]}",1)
start=body.index("    profile=d.get('game_module_build_profile',{})")
end=body.index("    entry={",start)
replacement=r'''    profile=d.get('game_module_build_profile',{})
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
'''
body=body[:start]+replacement+body[end:]
body=body.replace("    entry['game_ISA_provenance']=provenance", "    entry['binary_provenance']=provenance\n    entry['endpoint_evidence']=endpoints")
tail=r'''
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
'''
target=here/'AuditEndpointCacheReports.py'
target.write_text(header+body+tail,encoding='utf-8')
print(target)
