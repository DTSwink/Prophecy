"""Bounded whole-validator fixtures. Never rewrite historical inputs or emit benchmark acceptance."""
from pathlib import Path
from types import SimpleNamespace
import copy, datetime, hashlib, importlib.util, json, math

root=Path(__file__).resolve().parents[3]
draft=Path(__file__).resolve().parent
validator_path=draft/'Validate-PackagedNNCrowd-r5.py'
active_path=root/'Saved/JoltMigration/PackagedNNCrowdDraft/Validate-PackagedNNCrowd.py'
runner_path=root/'Saved/JoltMigration/NNCrowd-20260909-144331-647/Runs/Development-C2-20260909-183558-276/runner.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
runner=json.loads(runner_path.read_text(encoding='utf-8-sig'))
result_path=Path(runner['nativeResult']);package_path=Path(runner['packageResult'])
protected=[active_path,runner_path,result_path,package_path]
before={str(p):sha(p) for p in protected}
spec=importlib.util.spec_from_file_location('callback_r5_validator',validator_path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
args=SimpleNamespace(package=str(package_path),result=str(result_path),configuration='Development',count=2,warmup=60,samples=60,workers=7,padding=40.0,feedback_mode='Original',paused=False,pclass=True)
original_load=module.load
original=original_load(result_path)
valid=copy.deepcopy(original)
for policy in valid['passes'][0]['before']['actual_nn_scope']['root_capsule_policies']:
    policy['responses_by_channel']=[2]+[0]*31
valid['passes'][0]['multi_jolt_validation']['callback_kinematic_restore']={
 'success':True,'same_engine_frame':True,'native_ownership_removed_inside_callback':True,
 'class_change_waited_for_callback_return':True,'reentrant_modes_refused':True,
 'direct_component_cleanup_kinematic':True,
 'restored_anim_class':'/Script/GameAnimationSample3.ProphecyNNLocomotionAnimInstance',
 'probe_bone':'head','first_local_shift_cm':17.0,'second_local_shift_cm':24.0}
records=[]
def run(label,mutation=lambda r:None,accept=False,error_contains=None,seed=valid):
    fixture=copy.deepcopy(seed);mutation(fixture)
    module.load=lambda p: fixture if Path(p)==result_path else original_load(p)
    caught='';accepted=False
    try:
        outcome=module.validate(args)
        accepted=outcome['success'] is True
    except (ValueError,KeyError,TypeError,AttributeError) as exc:
        caught=f'{type(exc).__name__}: {exc}'
    passed=accepted==accept and (not error_contains or error_contains in caught)
    records.append(dict(name=label,expected_accept=accept,accepted=accepted,passed=passed,error=caught))
    if not passed:raise AssertionError(records[-1])

def restore(r):return r['passes'][0]['multi_jolt_validation']['callback_kinematic_restore']
def ray(r):return r['passes'][0]['multi_jolt_frames'][0]['agents'][0]['post_endphysics_queries']['center_ray']
def policy(r):return r['passes'][0]['before']['actual_nn_scope']['root_capsule_policies'][0]
run('original_historical_R4_is_rejected_unchanged',seed=original,error_contains='exactly 32')
run('synthetic_32_channels_without_restore_evidence_is_rejected',lambda r:r['passes'][0]['multi_jolt_validation'].pop('callback_kinematic_restore'),error_contains='Missing callback')
run('augmented_fixture_valid',accept=True)
for value in ('head','Head','HEAD','hEaD'):
    run('query_FName_accept_'+value,lambda r,v=value:ray(r).__setitem__('hit_bone',v),accept=True)
    run('restore_FName_accept_'+value,lambda r,v=value:restore(r).__setitem__('probe_bone',v),accept=True)
for label,value in [('wrong','pelvis'),('empty',''),('space',' head'),('suffix','head_0'),('integer',1),('bool',True),('null',None),('list',['head']),('object',{'name':'head'})]:
    run('query_FName_reject_'+label,lambda r,v=value:ray(r).__setitem__('hit_bone',v),error_contains='Head query receiver')
    run('restore_FName_reject_'+label,lambda r,v=value:restore(r).__setitem__('probe_bone',v),error_contains='not the head bone')
for label,values in [('33_zero',[2]+[0]*32),('33_nonzero',[2]+[0]*31+[128]),('31',[2]+[0]*30),('empty',[]),('wrong_first',[0]*32),('wrong_other',[2,1]+[0]*30),('boolean',[2,False]+[0]*30),('string',[2,'0']+[0]*30),('null',[2,None]+[0]*30),('nonfinite',[2,float('nan')]+[0]*30),('fractional',[2,0.5]+[0]*30),('not_list',{'0':2})]:
    run('stored_channels_reject_'+label,lambda r,v=values:policy(r).__setitem__('responses_by_channel',v),error_contains='exactly 32')
run('stored_channels_32_numeric_float_values_accept',lambda r:policy(r).__setitem__('responses_by_channel',[2.0]+[0.0]*31),accept=True)
for key in ('success','same_engine_frame','native_ownership_removed_inside_callback','class_change_waited_for_callback_return','reentrant_modes_refused','direct_component_cleanup_kinematic'):
    for label,value in [('false',False),('one',1),('string','true'),('null',None)]:
        run('restore_'+key+'_reject_'+label,lambda r,k=key,v=value:restore(r).__setitem__(k,v),error_contains=key)
    run('restore_'+key+'_missing',lambda r,k=key:restore(r).pop(k),error_contains=key)
for label,value in [('old_jolt','/Script/GameAnimationSample3.ProphecyJoltPoseAnimInstance'),('empty',''),('subclass','/Game/NNSubclass.NNSubclass_C'),('wrong_case','/Script/GameAnimationSample3.prophecynnlocomotionaniminstance'),('null',None),('integer',1)]:
    run('restored_class_reject_'+label,lambda r,v=value:restore(r).__setitem__('restored_anim_class',v),error_contains='exact native NN')
for key,expected in [('first_local_shift_cm',17),('second_local_shift_cm',24)]:
    for label,value in [('bool',True),('null',None),('string',str(expected)),('nan',float('nan')),('inf',float('inf')),('negative',-expected),('wrong',expected+1),('above_tolerance',expected+1.001e-5),('below_tolerance',expected-1.001e-5)]:
        run(key+'_reject_'+label,lambda r,k=key,v=value:restore(r).__setitem__(k,v),error_contains=key)
    run(key+'_missing',lambda r,k=key:restore(r).pop(k),error_contains=key)
    run(key+'_integer_accept',lambda r,k=key,v=expected:restore(r).__setitem__(k,v),accept=True)
    for label,value in [('next_double',math.nextafter(float(expected),float('inf'))),('inside_upper_tolerance',expected+0.999e-5),('inside_lower_tolerance',expected-0.999e-5)]:
        run(key+'_'+label+'_accept',lambda r,k=key,v=value:restore(r).__setitem__(k,v),accept=True)
for label,value in [('null',None),('array',[]),('string','success'),('boolean',True)]:
    run('restore_object_reject_'+label,lambda r,v=value:r['passes'][0]['multi_jolt_validation'].__setitem__('callback_kinematic_restore',v),error_contains='Missing callback')
module.load=original_load
after={str(p):sha(p) for p in protected}
assert before==after
output=dict(schema=1,success=True,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Whole-validator contract fixtures only. Historic R4 result is rejected unchanged. Accepted cases use a deliberately augmented IN-MEMORY fixture: exactly 32 responses and fabricated R5 callback evidence; they are not native runtime or benchmark acceptance.',fixture_baseline=str(result_path),validator=str(validator_path),validator_sha256=sha(validator_path),active_and_historical_inputs_unchanged=True,protected_sha256=after,test_count=len(records),accepted_fixture_count=sum(x['accepted'] for x in records),rejected_fixture_count=sum(not x['accepted'] for x in records),tests=records)
output_path=draft/('ValidatorFixtureAudit-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json')
with output_path.open('x',encoding='utf-8') as f:json.dump(output,f,indent=2,allow_nan=False)
print(json.dumps({k:output[k] for k in ('success','test_count','accepted_fixture_count','rejected_fixture_count','active_and_historical_inputs_unchanged')}))
print(str(output_path))
