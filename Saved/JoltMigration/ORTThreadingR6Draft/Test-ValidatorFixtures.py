"""R6 contract fixtures only: no launches and no historical/active mutations."""
from pathlib import Path
from types import SimpleNamespace
import copy,datetime,hashlib,importlib.util,json
r=Path(__file__).resolve().parents[3];d=Path(__file__).resolve().parent
vp=d/'Validate-PackagedNNCrowd.py'; runnerp=r/'Saved/JoltMigration/NNCrowd-20260909-144331-647/Runs/Development-C2-20260909-183558-276/runner.json'
runner=json.loads(runnerp.read_text(encoding='utf-8-sig'));resultp=Path(runner['nativeResult']);packagep=Path(runner['packageResult'])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
protected=[resultp,packagep,runnerp,r/'Saved/JoltMigration/PackagedNNCrowdDraft/Validate-PackagedNNCrowd.py',r/'Saved/JoltMigration/PackagedNNCrowdDraft/Run-NNCrowdPackage.ps1',r/'Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkNNJolt.cpp']
before={str(p):sha(p) for p in protected}
spec=importlib.util.spec_from_file_location('ort_r6',vp);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);real_load=m.load
original=real_load(resultp);package=real_load(packagep);base=copy.deepcopy(original)
for policy in base['passes'][0]['before']['actual_nn_scope']['root_capsule_policies']:policy['responses_by_channel']=[2]+[0]*31
base['passes'][0]['multi_jolt_validation']['callback_kinematic_restore']={'success':True,'same_engine_frame':True,'native_ownership_removed_inside_callback':True,'class_change_waited_for_callback_return':True,'reentrant_modes_refused':True,'direct_component_cleanup_kinematic':True,'restored_anim_class':'/Script/GameAnimationSample3.ProphecyNNLocomotionAnimInstance','probe_bone':'Head','first_local_shift_cm':17.,'second_local_shift_cm':24.}
def scope(x):return x['passes'][0]['before']['actual_nn_scope']
def capture(x,phase='before_models'):return scope(x)['ort_cpu_threading_'+phase]
def tuple_for(n):return f'(bUseGlobalThreadPool=False,IntraOpNumThreads={n},InterOpNumThreads=1,ExecutionMode=SEQUENTIAL)'
def seed(factor=0,configuration='Development'):
 x=copy.deepcopy(base);x['game_module_build_profile']['shipping_build']=configuration=='Shipping'
 row={'settings_class':'/Script/NNERuntimeORT.NNERuntimeORTSettings','selected_options':'GameThreadingOptions','use_global_thread_pool':False,'intra_op_num_threads':factor or 1,'inter_op_num_threads':1,'execution_mode':0,'execution_mode_name':'SEQUENTIAL','config_value_present':bool(factor),'commandline_ini_overrides_enabled':configuration=='Development','session_worker_execution_directly_observed':False}
 if factor:row['config_value']=tuple_for(factor)
 for phase in ('before_models','after_models'):scope(x)['ort_cpu_threading_'+phase]=copy.deepcopy(row)
 return x
records=[]
def test(name,mutate=lambda x:None,accept=False,factor=0,config='Development',contains=None,fixture=None):
 x=seed(factor,config) if fixture is None else copy.deepcopy(fixture);mutate(x)
 p=copy.deepcopy(package);p['configuration']=config
 m.load=lambda path:x if Path(path)==resultp else p if Path(path)==packagep else real_load(path)
 a=SimpleNamespace(package=str(packagep),result=str(resultp),configuration=config,count=2,warmup=60,samples=60,workers=7,padding=40.,feedback_mode='Original',paused=False,pclass=True,ort_intra_op_threads=factor)
 ok=False;error=''
 try:ok=m.validate(a)['success'] is True
 except (ValueError,KeyError,TypeError,AttributeError) as e:error=f'{type(e).__name__}: {e}'
 passed=(ok==accept) and (contains is None or contains in error)
 records.append(dict(name=name,expected_accept=accept,accepted=ok,passed=passed,error=error))
 if not passed:raise AssertionError(records[-1])
test('historic_R4_unchanged_rejected',fixture=original,contains='Missing ORT')
for factor in (0,1,2):test(f'Development_{factor}_valid_augmented_fixture',factor=factor,accept=True)
test('Shipping_0_valid_augmented_fixture',config='Shipping',accept=True)
for factor in (1,2):test(f'Shipping_{factor}_override_rejected',factor=factor,config='Shipping',contains='only by Development')
for factor in (-1,3,True):test(f'invalid_factor_{factor}',factor=factor,contains='factor must be')
for phase in ('before_models','after_models'):
 test(phase+'_missing',lambda x,p=phase:scope(x).pop('ort_cpu_threading_'+p),contains='Missing ORT')
 for key,value in [('settings_class','wrong'),('selected_options','EditorThreadingOptions'),('use_global_thread_pool',True),('use_global_thread_pool',0),('intra_op_num_threads',2),('intra_op_num_threads',True),('intra_op_num_threads',float('nan')),('intra_op_num_threads','1'),('inter_op_num_threads',2),('execution_mode',1),('execution_mode',False),('execution_mode_name','PARALLEL'),('commandline_ini_overrides_enabled',False),('commandline_ini_overrides_enabled',1),('session_worker_execution_directly_observed',True),('config_value_present',1),('config_value_present',True)]:
  test(phase+'_'+key+'_'+repr(value),lambda x,k=key,v=value,p=phase:capture(x,p).__setitem__(k,v),contains='ORT')
 test(phase+'_unclaimed_raw_value_rejected',lambda x,p=phase:capture(x,p).__setitem__('config_value','ignored'),contains='raw config')
 test(phase+'_override_missing_raw',lambda x,p=phase:capture(x,p).pop('config_value'),factor=2,contains='raw config')
 test(phase+'_override_wrong_tuple',lambda x,p=phase:capture(x,p).__setitem__('config_value',tuple_for(1)),factor=2,contains='not captured exactly')
 test(phase+'_override_not_reflected',lambda x,p=phase:capture(x,p).__setitem__('intra_op_num_threads',1),factor=2,contains='Unexpected ORT')
 test(phase+'_missing_thread_count',lambda x,p=phase:capture(x,p).pop('intra_op_num_threads'),contains='Unexpected ORT')
after={str(p):sha(p) for p in protected};assert before==after
out=dict(schema=1,success=True,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Whole-validator in-memory contract fixtures only. Accepted results deliberately fabricate future R6 ORT captures and R5 callback/32-channel evidence; Shipping positive fixture also fabricates its configuration/build flags. No native runtime acceptance or historic report rewrite.',validator_sha256=sha(vp),test_count=len(records),accepted_fixture_count=sum(t['accepted'] for t in records),rejected_fixture_count=sum(not t['accepted'] for t in records),active_and_historical_unchanged=True,protected_sha256=after,tests=records)
p=d/('ValidatorFixtures-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json');p.write_text(json.dumps(out,indent=2,allow_nan=False),encoding='utf-8');print(json.dumps({'success':True,'test_count':len(records),'report':str(p)}))
