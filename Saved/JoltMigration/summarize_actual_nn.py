import json
import sys
from pathlib import Path

for argument in sys.argv[1:]:
    report = json.loads(Path(argument).read_text(encoding='utf-8-sig'))
    result = {'report': argument, 'error': report.get('error'), 'count': report.get('count')}
    partial = report.get('failed_case_partial_measurements')
    if partial:
        result['partial'] = {k: v for k, v in partial.items() if k not in ('world_ms',)}
    result['passes'] = []
    for run in report.get('passes', []):
        validation = run.get('multi_jolt_validation', {})
        nn = run.get('actual_nn_validation', {})
        item = {'world_tick': run.get('world_tick'), 'success': validation.get('success'),
                'jolt_mean_ms': validation.get('mean_synchronous_jolt_step_ms'),
                'native_parts_mean_ms': validation.get('mean_native_step_parts_ms'),
                'phase_mean_ms': validation.get('mean_character_cpu_ms'),
                'nn_scalar_fields': {k: v for k, v in nn.items() if not isinstance(v, (dict, list))}}
        frames = run.get('multi_jolt_frames', [])
        item['recorded_frames'] = len(frames)
        if frames:
            jolt = frames[0].get('jolt', {})
            item['native_settings_first_frame'] = {k: jolt.get(k) for k in ('no_lock_idle_body_reads', 'worker_threads', 'job_concurrency')}
        paused = run.get('paused_chaos_diagnostic', {})
        if paused:
            item['paused_scene'] = {k: paused.get(k) for k in ('requested', 'applied', 'restored', 'validated_zero_delta_frames', 'error')}
        result['passes'].append(item)
    result['query_padding_at_finish'] = report.get('query_tree_settings_at_finish', {}).get('runtime_cvars', {}).get('p.aabbtree.DynamicTreeBoundingBoxPadding')
    if report.get('paused_chaos_diagnostic', {}).get('error'):
        result['paused_scene_error'] = report['paused_chaos_diagnostic']
    print(json.dumps(result, indent=2))
