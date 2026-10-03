"""Compare complete packaged runs offline. No launches, config edits, or sample filtering."""
import argparse
import collections
import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_VALIDATOR = ROOT / 'Saved/JoltMigration/PackagedNNCrowdDraft/Validate-PackagedNNCrowd.py'
TIMER_KEYS = ('build_seconds', 'inference_seconds', 'output_seconds', 'store_seconds')
COUNTER_KEYS = ('completed_nn_steps', 'completed_physical_samples', 'failed_physical_samples',
                'prepared_physical_samples', 'prepared_physical_batches')
TOP_KEYS = ('manager_tick_total', 'agent_tick_total', 'coordinator_total', 'world_other')
MANAGER_KEYS = ('nn_inference', 'manager_physical_resample', 'nn_build_excluding_resample',
                'nn_output', 'nn_store', 'manager_visual_roots', 'manager_other')

def load(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return json.load(stream, parse_constant=lambda s: (_ for _ in ()).throw(ValueError('Nonfinite JSON: '+s)))

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest().upper()

def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def integer(value):
    return finite(value) and value >= 0 and value == int(value)

def stats(values):
    if not values: return {'samples': 0}
    assert all(finite(v) for v in values)
    ordered = sorted(values); n = len(values)
    return {'samples': n, 'mean_ms': statistics.fmean(values), 'median_ms': statistics.median(values),
            'upper_median_ms': ordered[n//2], 'p95_ms': ordered[min(n-1, int(n*.95))],
            'max_ms': ordered[-1], 'min_ms': ordered[0], 'samples_above_10ms': sum(v>10 for v in values),
            'p95_order_index': min(n-1, int(n*.95))}

def group_rows(rows):
    result = {}
    for name, selected in [('total', rows), ('nn_step', [r for r in rows if r['nn_step']==1]),
                           ('interstitial', [r for r in rows if r['nn_step']==0])]:
        if not selected:
            result[name] = {'world': stats([])}
            continue
        phase_means = {k: statistics.fmean(r['phase_ms'][k] for r in selected) for k in selected[0]['phase_ms']}
        result[name] = {'world': stats([r['world_ms'] for r in selected]),
                        'world_partition_mean_ms': {k: phase_means[k] for k in TOP_KEYS},
                        'manager_partition_mean_ms': {k: phase_means[k] for k in MANAGER_KEYS},
                        'all_phase_mean_ms_including_overlapping_children': phase_means,
                        'phase_call_totals': {k: sum(r['phase_calls'][k] for r in selected) for k in selected[0]['phase_calls']},
                        'counter_delta_totals': {k: sum(r['nn_counter_deltas'][k] for r in selected) for k in COUNTER_KEYS}}
    return result

def argument_factors(arguments):
    # Remove only output destinations. Preserve every other explicit experiment/runtime factor.
    return ' '.join(re.sub(r'-(?:PhysicsBenchJson|abslog)=(?:"[^"]*"|\S+)', '', arguments, flags=re.I).split())

def analyze(runner_path, validator):
    runner_path = Path(runner_path).resolve(); runner = load(runner_path)
    package_path = Path(runner['packageResult']); package = load(package_path)
    report_path = Path(runner['nativeResult']); report = load(report_path)
    case = report['passes'][0]; frames = case['multi_jolt_frames']; worlds = case['world_ms']
    count = runner['count']; samples = runner['samples']; mode = runner['feedbackMode']; prepared = mode != 'Original'
    checks = {}; failures = {}
    def ck(name, condition, evidence=None):
        checks[name] = bool(condition)
        if not condition: failures[name] = evidence
    ck('runner_complete', runner['success'] is True and runner['exitCode']==0 and not runner['timedOut']
       and not runner['ownedKillIssued'] and not runner['failures'] and runner['validationSuccess'] is True)
    hashes = {'runner': digest(runner_path), 'package': digest(package_path), 'report': digest(report_path),
              'recorded_validation': digest(runner['validation'])}
    for key, expected in [('package', runner['packageSha256']), ('report', runner['nativeResultSha256']),
                          ('recorded_validation', runner['validationSha256'])]:
        ck(key+'_hash_matches_runner', hashes[key] == expected.upper())
    ck('runner_package_identity', runner['configuration']==package['configuration']
       and runner['snapshotSha256']==package['snapshotSha256']
       and runner['executableSha256']==package['executableSha256']
       and Path(runner['executable'])==Path(package['executable']))
    args = SimpleNamespace(package=str(package_path), result=str(report_path), configuration=runner['configuration'],
       count=count, warmup=runner['warmup'], samples=samples, workers=runner['joltWorkerThreads'],
       padding=runner['paddingCm'], feedback_mode=mode, paused=runner['pauseChaos'], pclass=runner['pClassGameThread'])
    try:
        fresh = validator.validate(args)
    except Exception as error:
        fresh = {'success': False, 'error': f'{type(error).__name__}: {error}'}
    ck('fresh_current_validator_pass', fresh.get('success') is True, fresh)
    ck('one_complete_pass_and_all_rows', len(report['passes'])==1 and len(frames)==len(worlds)==samples
       and case['samples']==samples and report['sample_frames']==samples)
    # Keep the two known R4 defects explicit even when the current validator stops at the first one.
    policies = case['before']['actual_nn_scope']['root_capsule_policies']
    ck('exact_32_valid_collision_responses', len(policies)==count and all(
       isinstance(p['responses_by_channel'], list) and len(p['responses_by_channel'])==32
       and all(finite(v) and v in (0,1,2) for v in p['responses_by_channel'])
       and p['responses_by_channel']==[2]+[0]*31 for p in policies),
       dict(entry_count_histogram=dict(collections.Counter(len(p['responses_by_channel']) for p in policies))))
    restoration = case['multi_jolt_validation'].get('callback_kinematic_restore')
    restore_flags = ('success', 'same_engine_frame', 'native_ownership_removed_inside_callback',
       'class_change_waited_for_callback_return', 'reentrant_modes_refused', 'direct_component_cleanup_kinematic')
    ck('callback_restore_evidence_present', isinstance(restoration, dict) and all(restoration.get(k) is True for k in restore_flags), restoration)
    previous = case['before']['actual_nn_initial']; initial = previous; rows = []; calls_total=collections.Counter()
    counter_ok = timer_ok = cadence_calls_ok = native_ok = queries_ok = phases_ok = identity_ok = True
    coverage = collections.Counter(); captures = case['before']['multi_jolt_handoff']['source_captures']
    expected_mode={'Original':0,'PreparedSerial':1,'PreparedParallel':2}[mode]
    for i in range(len(frames)):
        f=frames[i]; world=worlds[i]; current=f['actual_nn']; calls=f['character_cpu_calls']; phase=dict(f['character_cpu_ms'])
        deltas={k:current[k]-previous[k] for k in COUNTER_KEYS}; step=deltas['completed_nn_steps']
        timers={k.removesuffix('_seconds'):1000*(current[k]-previous[k]) for k in TIMER_KEYS}
        counter_ok &= all(integer(current[k]) and integer(previous[k]) for k in COUNTER_KEYS)
        counter_ok &= step in (0,1) and deltas['completed_physical_samples']==count*step and current['failed_physical_samples']==0
        counter_ok &= deltas['prepared_physical_samples']==(count*step if prepared else 0) and deltas['prepared_physical_batches']==(step if prepared else 0)
        counter_ok &= current['physical_feedback_mode']==expected_mode and (prepared or current['prepared_physical_samples']==current['prepared_physical_batches']==0)
        timer_ok &= all(finite(v) and v>=-1e-9 for v in timers.values()) and (step==1 or all(abs(v)<1e-9 for v in timers.values()))
        phases_ok &= finite(world) and world>0 and all(finite(v) and v>=0 for v in phase.values()) and all(integer(v) for v in calls.values())
        expected_calls={'manager_tick_total':1, 'manager_visual_roots':1, 'manager_physical_resample':step,
          'manager_pose_publish':count*step,'physical_sample_read':count*step,
          'physical_raw_encode':0 if prepared else 2*count*step, 'physical_feedback_prepare':count*step if prepared else 0,
          'physical_feedback_batch_wall':step if prepared else 0,'compose_batch_wall':1,'compose':0,'fixture_pose_publish':0,
          'pose_proxy_preupdate':count,'pose_proxy_preevaluate':count,'pose_proxy_evaluate':count,
          'pose_proxy_postevaluate_base':count,'pose_finalize_after_query':count,'pose_publication_validation':6*count,
          'refresh_bones':count,'query_update':count,'agent_tick_total':count,'target_endpoint_expand':count}
        cadence_calls_ok &= all(calls.get(k)==v for k,v in expected_calls.items())
        native=f['jolt']; native_ok &= f['sample_frame']==i and native['completed_steps']==i+1 and native['active_bodies']==22*count
        native_ok &= native['bodies']==22*count+1 and native['constraints']==21*count and f['chaos_dynamic_bodies']==0
        native_ok &= f['coordinator_characters']==count and f['validated_dynamic_rig_bodies']==22*count and f['validated_skeleton_bones']==88*count
        native_ok &= abs(native['last_step_ms']-sum(v for k,v in native['step_parts_ms'].items() if k!='post_update_validation'))<1e-6
        frame_coverage=collections.Counter(agent_records=len(f['agents']), dynamic_body_checks=f['validated_dynamic_rig_bodies'], skeleton_bone_checks=f['validated_skeleton_bones'])
        for a in f['agents']:
            q=a['post_endphysics_queries']; ray=q['center_ray']; lane=a['agent_index']
            frame_coverage['query_body_checks']+=q['validated_query_bodies']; frame_coverage['head_rays']+=int(ray['success'])
            identity_ok &= 0<=lane<len(captures) and ray['hit_component']==captures[lane]['physical_component']
            queries_ok &= q['success'] is True and q['normal_unfiltered_head_visibility_exercised'] is True and q['validation_only_ignored_own_capsule'] is False
            queries_ok &= ray['success'] is True and ray['validation_only_capsule_filter'] is False and ray['hit_bone'].casefold()=='head'
            queries_ok &= q['observed_world_tick_group']==7 and q['own_root_is_capsule'] is True and q['own_blocking_capsule_shapes']==1
            queries_ok &= q['max_query_bone_position_cm']<=.02 and q['max_query_bone_angle_degrees']<=.02
        coverage.update(frame_coverage); calls_total.update(calls)
        phase.update({'nn_'+k:v for k,v in timers.items()})
        phase['nn_build_excluding_resample']=timers['build']-phase['manager_physical_resample']
        phase['nn_store_outside_pose_publish']=timers['store']-phase['manager_pose_publish']
        phase['manager_other']=phase['manager_tick_total']-phase['manager_visual_roots']-sum(timers.values())
        phase['world_other']=world-sum(phase[k] for k in TOP_KEYS if k!='world_other')
        timer_ok &= all(phase[k]>=-1e-5 for k in ('nn_build_excluding_resample','nn_store_outside_pose_publish','manager_other','world_other'))
        rows.append({'sample_frame':i,'engine_frame':f['validation_engine_frame'],'world_ms':world,'nn_step':step,
          'nn_counters':{k:current[k] for k in COUNTER_KEYS},'nn_counter_deltas':deltas,'nn_timer_delta_ms':timers,
          'loaded_runtime_and_batch':{k:current[k] for k in ('run_runtime','walk_runtime','upper_runtime','run_batch_size','walk_batch_size','upper_batch_size','foot_roll_steps','physical_feedback_mode')},
          'phase_ms':phase,'phase_calls':calls,'native_step_parts_ms':native['step_parts_ms'],
          'native_counts':{k:native[k] for k in ('bodies','active_bodies','constraints','completed_steps')},'coverage':dict(frame_coverage)})
        previous=current
    ck('all_counter_deltas_and_feedback_mode',counter_ok)
    ck('all_NN_timer_deltas_finite_and_nested',timer_ok)
    ck('all_phase_times_and_calls_valid',phases_ok)
    ck('all_phase_calls_match_actual_work',cadence_calls_ok)
    ck('all_native_counts_and_timer_partition',native_ok)
    ck('all_unfiltered_query_coverage',queries_ok)
    ck('all_exact_per_lane_query_receivers',identity_ok)
    ck('exact_half_rate_NN_groups',sum(r['nn_step'] for r in rows)==samples//2 and all(a['nn_step']!=b['nn_step'] for a,b in zip(rows,rows[1:])))
    ck('complete_coverage_totals',coverage=={'agent_records':count*samples,'dynamic_body_checks':22*count*samples,
      'skeleton_bone_checks':88*count*samples,'query_body_checks':22*count*samples,'head_rays':count*samples})
    ck('cumulative_timers_match_summary',all(abs(statistics.fmean(r['nn_timer_delta_ms'][k.removesuffix('_seconds')] for r in rows)-case['actual_nn_validation']['mean_nn_'+k.removesuffix('_seconds')+'_ms_per_world_frame'])<1e-8 for k in TIMER_KEYS))
    controls={k:runner[k] for k in ('configuration','count','warmup','samples','pClassGameThread','pauseChaos','joltWorkerThreads','paddingCm','feedbackMode','requestedPriority','snapshotSha256','executableSha256')}
    controls['arguments_except_output_paths']=argument_factors(runner['arguments'])
    return {'runner':str(runner_path),'report':str(report_path),'package':str(package_path),'hashes':hashes,
      'recorded_validator_sha256':runner['validatorSha256'],'controls':controls,
      'accepted_for_comparison':all(checks.values()),'checks':checks,'failed_checks':failures,'fresh_validator':fresh,
      'loaded_model_scope':'Run/walk/upper runtime and batch fields describe loaded instances, not per-model invocation counts. This walking fixture invokes Walk and Upper; Run is loaded. No three-inference claim is inferred from these fields.',
      'initial_NN_counters':{k:initial[k] for k in COUNTER_KEYS},'final_NN_counters':{k:previous[k] for k in COUNTER_KEYS},
      'counter_delta_totals':{k:previous[k]-initial[k] for k in COUNTER_KEYS},'coverage_totals':dict(coverage),
      'phase_call_totals':dict(calls_total),'groups':group_rows(rows),'rows':rows}

def summarize_repeats(runs):
    buckets=collections.defaultdict(list)
    for run in runs:
        if 'controls' in run: buckets[json.dumps(run['controls'],sort_keys=True)].append(run)
    result=[]
    for key, repeated in buckets.items():
        entries={}
        for name in ('total','nn_step','interstitial'):
            available=[r['groups'][name]['world'] for r in repeated if r['groups'][name]['world']['samples']]
            if not available:
                entries[name]={'individual_run_world_stats': [], 'samples': 0}
                continue
            entries[name]={'individual_run_world_stats':available,'mean_of_run_means_ms':statistics.fmean(v['mean_ms'] for v in available),
              'min_run_mean_ms':min(v['mean_ms'] for v in available),'max_run_mean_ms':max(v['mean_ms'] for v in available),
              'worst_run_p95_ms':max(v['p95_ms'] for v in available),'worst_run_max_ms':max(v['max_ms'] for v in available)}
        result.append({'controls':json.loads(key),'run_count':len(repeated),'runners':[r['runner'] for r in repeated],
          'all_runs_accepted':all(r['accepted_for_comparison'] for r in repeated),'by_frame_class':entries,
          'pooled_all_samples':group_rows([row for run in repeated for row in run['rows']]),
          'scope':'Recorded controls and binary identity match. Unknown runtime configuration, clocks and scheduling are not proven equal. Every run and all samples remain visible; pooled statistics never replace per-run tails.'})
    return result

def write_markdown(result, path):
    lines=['# Packaged repeat-run timing comparison','',
      'Every timed row is retained. Failed gates remain failures; their timing is diagnostic only. Development and Shipping are separate controls. Median averages the two central samples; upper median and the exact p95 order index are also retained in JSON.','',
      '| Run | Configuration | Accepted gates | Frame class | N | Mean ms | Median ms | p95 ms | Max ms | >10 ms |',
      '|---|---|---|---|---:|---:|---:|---:|---:|---:|']
    for run in result['runs']:
        if 'groups' not in run:
            lines += [f"| {Path(run['runner']).parent.name} | unknown | FAIL | unavailable | 0 | | | | | |"]
            continue
        for name,g in run['groups'].items():
            s=g['world']
            lines.append(f"| {Path(run['runner']).parent.name} | {run['controls']['configuration']} | {'PASS' if run['accepted_for_comparison'] else 'FAIL'} | {name} | {s['samples']} | {s.get('mean_ms',0):.6f} | {s.get('median_ms',0):.6f} | {s.get('p95_ms',0):.6f} | {s.get('max_ms',0):.6f} | {s.get('samples_above_10ms',0)} |")
    lines += ['', 'The JSON keeps disjoint manager/agent/coordinator/world-remainder partitions, a separate manager partition, all overlapping child phases, every counter delta/call, source hashes and repeat groups. Native wrapper, composition and RefreshBones are children of coordinator; query publication is inside RefreshBones. NN build includes physical resampling, and NN store includes pose publication.', '',
       'Loaded Run/Walk/Upper batch-100 identities do not mean three inference calls: the walking fixture uses Walk plus Upper. Actual model work remains required.', '',
       'Runner/package/report/validation hashes and current strict validation are checked. This tool does not independently rehash staged executables, DLLs, cooked packages or loaded memory; package provenance audits remain separate. No rendering, active blood-pixel or complete-migration claim follows from these NullRHI timings.','']
    for run in result['runs']:
        if not run['accepted_for_comparison']:
            lines += [f"Failed gates for `{run['runner']}`:", '```json',json.dumps(run.get('failed_checks',run.get('error')),indent=2),'```','']
    with path.open('x',encoding='utf-8') as stream: stream.write('\n'.join(lines))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runners',nargs='+',type=Path)
    parser.add_argument('--validator',type=Path,default=DEFAULT_VALIDATOR)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--markdown',type=Path,required=True)
    args=parser.parse_args()
    resolved=[p.resolve() for p in args.runners]
    if len(set(resolved))!=len(resolved): parser.error('Duplicate runner paths would duplicate samples.')
    if args.output.exists() or args.markdown.exists(): parser.error('Output files must be new; existing evidence is never overwritten.')
    spec=importlib.util.spec_from_file_location('packaged_runtime_validator',args.validator.resolve())
    validator=importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
    result={'schema':1,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'tool':str(Path(__file__).resolve()),'tool_sha256':digest(__file__),
      'validator':str(args.validator.resolve()),'validator_sha256':digest(args.validator),
      'scope':'Read-only complete-row timing comparison; acceptance requires every recorded runner/current-validator/supplemental gate. Historical failures are retained. No UE, build or settings changes.', 'runs':[]}
    for runner in resolved:
        try: result['runs'].append(analyze(runner,validator))
        except Exception as error:
            result['runs'].append({'runner':str(runner),'accepted_for_comparison':False,'error':f'{type(error).__name__}: {error}'})
    result['all_runs_accepted']=all(r['accepted_for_comparison'] for r in result['runs'])
    result['repeat_groups']=summarize_repeats(result['runs'])
    with args.output.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2,allow_nan=False)
    write_markdown(result,args.markdown)
    print(json.dumps({'all_runs_accepted':result['all_runs_accepted'],'runs':len(result['runs']),'output':str(args.output),'markdown':str(args.markdown)}))
    return 0 if result['all_runs_accepted'] else 1

if __name__=='__main__': raise SystemExit(main())
