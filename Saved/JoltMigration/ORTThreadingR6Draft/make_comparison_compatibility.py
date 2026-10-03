"""Create only separately owned R6 comparison drafts; do not modify active tooling."""
import datetime, difflib, hashlib, json
from pathlib import Path
here=Path(__file__).resolve().parent
root=here.parents[2]
relative='Saved/JoltMigration/PackagedR5ComparisonDraft/ComparePackagedRuns.py'
source=root/relative
validator=root/'Saved/JoltMigration/PackagedNNCrowdDraft/Validate-PackagedNNCrowd.py'
original=source.read_bytes(); text=original.decode('utf-8')
def replace(old,new):
    global text
    assert text.count(old)==1,old
    text=text.replace(old,new)
replace("    count = runner['count']; samples = runner['samples']; mode = runner['feedbackMode']; prepared = mode != 'Original'\n",
"    count = runner['count']; samples = runner['samples']; mode = runner['feedbackMode']; prepared = mode != 'Original'\n"
"    ort_override = runner.get('ortIntraOpThreadsOverride', 0)\n"
"    ort_tuple = runner.get('ortStartupTuple')\n")
replace("    ck('runner_complete', runner['success'] is True",
"    expected_ort_tuple = ('(bUseGlobalThreadPool=False,IntraOpNumThreads=' + str(ort_override)\n"
"                          + ',InterOpNumThreads=1,ExecutionMode=SEQUENTIAL)') if ort_override else None\n"
"    ort_prefix = '-ini:Engine:[/Script/NNERuntimeORT.NNERuntimeORTSettings]:GameThreadingOptions='\n"
"    ck('requested_ORT_factor_and_tuple_recorded', isinstance(ort_override, int) and not isinstance(ort_override, bool)\n"
"       and ort_override in (0,1,2) and ort_tuple == expected_ort_tuple\n"
"       and (not ort_override or runner['configuration']=='Development')\n"
"       and (runner['arguments'].count(ort_prefix)==1 and ort_prefix+expected_ort_tuple in runner['arguments']\n"
"            if ort_override else ort_prefix not in runner['arguments']),\n"
"       {'requested_factor':ort_override,'recorded_tuple':ort_tuple})\n"
"    ck('runner_complete', runner['success'] is True")
replace("       padding=runner['paddingCm'], feedback_mode=mode, paused=runner['pauseChaos'], pclass=runner['pClassGameThread'])\n",
"       padding=runner['paddingCm'], feedback_mode=mode, paused=runner['pauseChaos'], pclass=runner['pClassGameThread'],\n"
"       ort_intra_op_threads=ort_override)\n")
replace("    controls['arguments_except_output_paths']=argument_factors(runner['arguments'])\n",
"    controls['arguments_except_output_paths']=argument_factors(runner['arguments'])\n"
"    controls['ortIntraOpThreadsOverride']=ort_override\n"
"    controls['ortStartupTuple']=ort_tuple\n"
"    scope=case['before']['actual_nn_scope']\n"
"    controls['ort_selected_settings_before_models']=scope.get('ort_cpu_threading_before_models')\n"
"    controls['ort_selected_settings_after_models']=scope.get('ort_cpu_threading_after_models')\n")
files={
 'ComparePackagedRuns.py':text.encode('utf-8'),
 'ComparePackagedRuns-R5-Archive.py':original,
 'Validate-PackagedNNCrowd-R5-ComparisonArchive.py':validator.read_bytes(),
 'ComparisonCompatibility.patch':''.join(difflib.unified_diff(original.decode().splitlines(True),text.splitlines(True),fromfile='a/'+relative,tofile='b/'+relative)).encode('utf-8')}
for name,content in files.items():
    with (here/name).open('xb') as stream:stream.write(content)
sha=lambda b:hashlib.sha256(b).hexdigest().upper()
result={'status':'DRAFT_ONLY_NOT_PROMOTED_NO_UE','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'active_comparator':str(source),'baseline_sha256':sha(original),'draft_sha256':sha(files['ComparePackagedRuns.py']),
 'archived_R5_validator_source':str(validator),'archived_R5_validator_sha256':sha(files['Validate-PackagedNNCrowd-R5-ComparisonArchive.py']),
 'files':{name:sha(content) for name,content in files.items()},
 'scope':'Adds the recorded requested ORT factor to the current validator call, and factor/tuple/full before-after captures to comparison groups. Missing old-run factor defaults to zero. An archived R5 validator can still validate old reports; an R6 validator still intentionally rejects missing R6 captures.'}
with (here/'ComparisonCompatibilityEvidence.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
print(json.dumps({'baseline':result['baseline_sha256'],'draft':result['draft_sha256']}))
