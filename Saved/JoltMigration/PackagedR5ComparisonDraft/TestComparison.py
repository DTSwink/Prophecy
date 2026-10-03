"""Offline aggregation controls; synthetic copies below are tests, never new runs."""
import importlib.util
import json
from pathlib import Path

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('comparison',here/'ComparePackagedRuns.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
historical=m.load(here/'HistoricalR4Test.json'); r=historical['runs'][0]
tests={}
def ck(name, value):
    tests[name]=bool(value)
    assert value, name
ck('historical_rejected',historical['all_runs_accepted'] is False and not r['accepted_for_comparison'])
ck('only_known_R4_failures',set(r['failed_checks'])=={'fresh_current_validator_pass','exact_32_valid_collision_responses','callback_restore_evidence_present'})
ck('all_360_rows_retained',len(r['rows'])==360 and [v['sample_frame'] for v in r['rows']]==list(range(360)))
ck('180_NN_180_interstitial',r['groups']['nn_step']['world']['samples']==r['groups']['interstitial']['world']['samples']==180)
ck('all_timed_outliers_retained',r['groups']['total']['world']['max_ms']==18.379002809524536 and r['rows'][0]['world_ms']==18.379002809524536)
ck('total_mean_matches_historical',abs(r['groups']['total']['world']['mean_ms']-9.471365540391869)<1e-12)
ck('NN_mean_matches_historical',abs(r['groups']['nn_step']['world']['mean_ms']-11.537586131857502)<1e-12)
ck('median_definitions_distinguished',r['groups']['total']['world']['median_ms']==9.955348446965218 and r['groups']['total']['world']['upper_median_ms']==10.352697223424911)
ck('body_bone_query_feedback_counts_retained',r['coverage_totals']=={'agent_records':36000,'dynamic_body_checks':792000,'skeleton_bone_checks':3168000,'query_body_checks':792000,'head_rays':36000} and r['counter_delta_totals']['completed_physical_samples']==18000)
ck('world_partition_closes',all(abs(sum(v['world_partition_mean_ms'].values())-v['world']['mean_ms'])<1e-12 for v in r['groups'].values()))
ck('manager_partition_closes',all(abs(sum(v['manager_partition_mean_ms'].values())-v['world_partition_mean_ms']['manager_tick_total'])<1e-12 for v in r['groups'].values()))
copy={**r,'runner':'SYNTHETIC_AGGREGATION_TEST_COPY_B'}
repeat=m.summarize_repeats([r,copy])
ck('synthetic_repeat_aggregation_keeps_every_row',len(repeat)==1 and repeat[0]['run_count']==2 and repeat[0]['pooled_all_samples']['total']['world']['samples']==720)
ck('synthetic_repeat_counter_sums',repeat[0]['pooled_all_samples']['total']['counter_delta_totals']['completed_physical_samples']==36000 and repeat[0]['pooled_all_samples']['nn_step']['phase_call_totals']['physical_feedback_batch_wall']==0)
ck('historical_failure_not_laundered_by_pooling',repeat[0]['all_runs_accepted'] is False)
shipping={**copy,'controls':{**r['controls'],'configuration':'SYNTHETIC_SHIPPING_GROUP_TEST'}}
ck('configurations_never_pooled',len(m.summarize_repeats([r,shipping]))==2)
binary={**copy,'controls':{**r['controls'],'executableSha256':'SYNTHETIC_DIFFERENT_BINARY'}}
ck('different_binaries_never_pooled',len(m.summarize_repeats([r,binary]))==2)
factor={**copy,'controls':{**r['controls'],'arguments_except_output_paths':r['controls']['arguments_except_output_paths']+' -UnrecognizedFactor=2'}}
ck('unknown_explicit_factor_prevents_pooling',len(m.summarize_repeats([r,factor]))==2)
ck('only_output_destinations_removed',m.argument_factors('-nullrhi -PhysicsBenchJson="C:/a b/out.json" -abslog="C:/logs/x.log" -ini:Engine:X=2')=='-nullrhi -ini:Engine:X=2')
result={'status':'OFFLINE_TESTS_ONLY_NOT_NEW_RUNTIME_MEASUREMENTS','success':all(tests.values()),'tests':tests,
        'historical_result_sha256':m.digest(here/'HistoricalR4Test.json'),'current_comparison_tool_sha256':m.digest(here/'ComparePackagedRuns.py'),
        'scope':'Historical R4 gate failures retained. Synthetic in-memory copies verify aggregation only; no report data or source is changed, no UE/build runs.'}
with (here/'ComparisonTests.json').open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2)
print(json.dumps({'success':result['success'],'checks':len(tests)}))
