"""Offline comparison compatibility controls; no synthetic runtime results are emitted."""
import ast, importlib.util, json
from pathlib import Path
here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r6comparison',here/'ComparePackagedRuns.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
old=m.load(here/'ComparisonR5ArchiveControl.json'); required=m.load(here/'ComparisonR6MissingCaptureControl.json')
r=old['runs'][0]; tests={}
def ck(name,value):
    tests[name]=bool(value)
    assert value,name
ck('unmodified_R5_passes_archived_R5_validator',old['all_runs_accepted'] is True and all(r['checks'].values()))
ck('old_runner_missing_factor_defaults_zero',r['controls']['ortIntraOpThreadsOverride']==0 and r['controls']['ortStartupTuple'] is None)
ck('old_report_missing_capture_remains_explicit_null',r['controls']['ort_selected_settings_before_models'] is None and r['controls']['ort_selected_settings_after_models'] is None)
ck('R6_validator_rejects_missing_capture',required['all_runs_accepted'] is False and set(required['runs'][0]['failed_checks'])=={'fresh_current_validator_pass'}
   and required['runs'][0]['fresh_validator']['error']=='ValueError: Missing ORT selected threading capture before_models.')
ck('R6_validation_reached_capture_gate_not_AttributeError','AttributeError' not in required['runs'][0]['fresh_validator']['error'])
ck('same_source_report_and_all_rows_preserved',r['hashes']['report']==required['runs'][0]['hashes']['report'] and len(r['rows'])==len(required['runs'][0]['rows'])==360
   and r['groups']==required['runs'][0]['groups'])
module=ast.parse((here/'ComparePackagedRuns.py').read_text())
namespace_calls=[n for n in ast.walk(module) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='SimpleNamespace']
ck('selected_runner_factor_forwarded_to_validator',len(namespace_calls)==1 and any(k.arg=='ort_intra_op_threads' and isinstance(k.value,ast.Name) and k.value.id=='ort_override' for k in namespace_calls[0].keywords))
copy={**r,'runner':'SYNTHETIC_GROUPING_CONTROL_NOT_A_NEW_RUN'}
def separate(field,value):
    candidate={**copy,'controls':{**r['controls'],field:value}}
    return len(m.summarize_repeats([r,candidate]))==2
ck('requested_factor_alone_separates_groups',separate('ortIntraOpThreadsOverride',2))
ck('recorded_tuple_alone_separates_groups',separate('ortStartupTuple','SYNTHETIC_TUPLE'))
ck('before_settings_alone_separate_groups',separate('ort_selected_settings_before_models',{'intra_op_num_threads':2}))
ck('after_settings_alone_separate_groups',separate('ort_selected_settings_after_models',{'intra_op_num_threads':2}))
baseline=m.load(here/'ComparisonCompatibilityEvidence.json')
ck('active_comparator_not_modified',m.digest(baseline['active_comparator'])==baseline['baseline_sha256'])
ck('R5_validator_archive_exact',m.digest(here/'Validate-PackagedNNCrowd-R5-ComparisonArchive.py')==baseline['archived_R5_validator_sha256']=='1121670470BC9E9465E2EB8213162E5E5E72AEFBD3F68D781E732E293EEDA56C')
ck('draft_exact_hash',m.digest(here/'ComparePackagedRuns.py')==baseline['draft_sha256'])
result={'status':'OFFLINE_COMPATIBILITY_TESTS_ONLY','success':all(tests.values()),'tests':tests,
  'R5_control_sha256':m.digest(here/'ComparisonR5ArchiveControl.json'),'R6_missing_capture_control_sha256':m.digest(here/'ComparisonR6MissingCaptureControl.json'),
  'draft_sha256':baseline['draft_sha256'],'scope':'Both controls reread the same real R5 run. No new UE measurement, source edit, settings application or forged R6 acceptance. Synthetic in-memory changes verify grouping keys only.'}
with (here/'ComparisonCompatibilityTests.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
print(json.dumps({'success':result['success'],'checks':len(tests)}))
