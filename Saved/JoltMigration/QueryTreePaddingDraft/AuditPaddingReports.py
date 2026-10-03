"""Read-only audit of the three retained padding runs; writes only this draft's JSON."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
FILES = [
    (5, 'nn_jolt_padding5_A_100_20260909_1415.json'),
    (20, 'nn_jolt_padding20_A_100_20260909_1416.json'),
    (40, 'nn_jolt_padding40_A_100_20260909_1417.json'),
]
PADDING = 'p.aabbtree.DynamicTreeBoundingBoxPadding'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def near(a, b):
    return abs(a - b) <= 1.e-9


def audit(padding, filename):
    path = PROJECT / 'Saved' / 'Benchmarks' / filename
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    report = json.loads(raw.decode('utf-8-sig'))
    require(report['error'] == '', 'Top-level error')
    require(report['count'] == 100 and report['sample_frames'] == 360, 'Fixture dimensions')
    require(report['fixed_dt'] == 1 / 60, 'Fixed delta')
    require(report['nullrhi'] and report['movement_only'], 'Renderer/movement profile')
    require(not report['substepping'] and not report['async_physics'], 'Physics scheduling')
    require(len(report['passes']) == 1, 'Expected one pass')
    case = report['passes'][0]
    require(case['mode'] == 'NNJoltCrowd' and case['fixture'] == 'floor_gravity', 'Wrong method')
    require(case['samples'] == len(case['world_ms']) == 360, 'World samples')
    values = sorted(case['world_ms'])
    require(all(math.isfinite(x) and x >= 0 for x in values), 'Invalid world timing')
    require(near(sum(values) / len(values), case['world_tick']['mean_ms']), 'Mean mismatch')
    require(values[len(values) // 2] == case['world_tick']['median_ms'], 'Median mismatch')
    require(values[int(.95 * len(values))] == case['world_tick']['p95_ms'], 'P95 mismatch')
    snapshots = [case['before']['query_tree_settings'], case['after']['query_tree_settings'],
                 report['query_tree_settings_at_finish']]
    for snapshot in snapshots:
        require(snapshot['padding_override_requested'], 'Padding not explicitly requested')
        require(float(snapshot['requested_padding_cm_text']) == padding, 'Requested value differs')
        require(snapshot['runtime_cvars'][PADDING] == padding, 'Effective value differs')
    require(snapshots[0]['runtime_cvars'] == snapshots[1]['runtime_cvars'] == snapshots[2]['runtime_cvars'],
            'CVar settings changed across boundaries')
    for boundary in ['before', 'after']:
        require(case[boundary]['skeletal_actor_spatial_buckets'] == {'bucket_0_inner_1': 2200},
                'Native actor bucket mismatch')

    validation = case['multi_jolt_validation']
    actual = case['actual_nn_validation']
    require(validation['success'] and actual['success'], 'Final validation failed')
    require(actual['completed_nn_steps'] == 180 and actual['completed_physical_samples'] == 18000,
            'Measured NN/feedback counts')
    require(actual['minimum_managed_root_travel_cm'] >= 1200, 'Managed root did not travel')
    require(validation['characters'] == 100 and validation['frames'] == 360
            and validation['bones_per_character'] == 88, 'Character dimensions')
    frames = case['multi_jolt_frames']
    require(len(frames) == 360, 'Incomplete character rows')
    counts = Counter({'capsule_filtered_rows': 0, 'normal_unfiltered_rows': 0})
    begin_cpus, end_cpus, refresh_cpus = Counter(), Counter(), Counter()
    phases = Counter()
    fallback_agents, fallback_frames = set(), set()
    previous_nn = previous_physical = None
    runtime_sets = {name: set() for name in ['run_runtime', 'walk_runtime', 'upper_runtime',
                    'run_batch_size', 'walk_batch_size', 'upper_batch_size', 'foot_roll_steps']}
    for index, frame in enumerate(frames):
        require(frame['sample_frame'] == index and frame['success'], 'Frame sequence/success')
        require(frame['coordinator_characters'] == 100 and frame['chaos_dynamic_bodies'] == 0,
                'Ownership/coordinator count')
        require(frame['automatic_step_count'] == index + 1, 'Automatic step sequence')
        require(frame['automatic_step_engine_frame'] == frame['validation_engine_frame'],
                'Automatic step is from another engine frame')
        require(all(frame[key] == 2 for key in ['automatic_tick_group', 'actual_automatic_tick_group',
                    'actual_automatic_end_tick_group', 'automatic_observed_world_tick_group']), 'Tick group')
        native = frame['jolt']
        require(native['initialized'] and not native['faulted'] and native['update_error_bits'] == 0,
                'Native update error')
        require(native['completed_steps'] == index + 1 and native['bodies'] == 2201
                and native['constraints'] == 2100 and native['last_collision_steps'] == 1,
                'Native body/joint/step count')
        require(frame['validated_dynamic_rig_bodies'] == 2200 and frame['validated_skeleton_bones'] == 8800,
                'Missing body/bone coverage')
        require(len(frame['agents']) == 100 and {a['agent_index'] for a in frame['agents']} == set(range(100)),
                'Missing/duplicate agent')
        for agent in frame['agents']:
            counts['character_rows'] += 1
            require(agent['success'] and agent['validated_dynamic_rig_bodies'] == 22
                    and agent['validated_skeleton_bones'] == 88, 'Per-agent pose coverage')
            require(agent['completed_revision'] == frame['completed_revision'], 'Stale completed pose')
            require(agent['max_feedback_render_position_cm'] <= validation['position_tolerance_cm']
                    and agent['max_feedback_render_angle_degrees'] <= validation['angle_tolerance_degrees']
                    and agent['max_feedback_render_scale_difference'] <= validation['scale_tolerance'],
                    'Pose agreement tolerance')
            query = agent['post_endphysics_queries']
            require(query['success'] and query['validated_query_bodies'] == 22
                    and query['observed_world_tick_group'] == 7, 'Post-EndPhysics query coverage')
            require(query['own_root_is_capsule'] and query['own_blocking_capsule_shapes'] == 1,
                    'Actual capsule proof')
            require(query['capsule_native_component_position_error_cm'] <= .02
                    and query['capsule_native_component_angle_error_degrees'] <= .02, 'Capsule pose mismatch')
            center = query['center_ray']
            require(center['success'] and center['hit_bone'] == 'head'
                    and center['hit_component'].endswith('.PhysicalMesh'), 'Wrong head receiver')
            filtered = query['validation_only_ignored_own_capsule']
            require(filtered == center['validation_only_capsule_filter'], 'Filtered query metadata mismatch')
            require(query['normal_unfiltered_head_visibility_exercised'] != filtered, 'Visibility classification')
            counts['capsule_filtered_rows' if filtered else 'normal_unfiltered_rows'] += 1
            if filtered:
                fallback_agents.add(agent['agent_index'])
                fallback_frames.add(index)
            counts['disjoint_previous_aabb_rows'] += int(query['disjoint_previous_aabb_ray'])
            counts['native_query_body_checks'] += query['validated_query_bodies']
            counts['full_bone_checks'] += agent['validated_skeleton_bones']
        nn = frame['actual_nn']
        require(nn['failed_physical_samples'] == 0 and nn['completed_physical_samples'] == 100 * nn['completed_nn_steps'],
                'NN physical feedback missing/failing')
        if previous_nn is not None:
            delta = nn['completed_nn_steps'] - previous_nn
            require(delta in (0, 1) and nn['completed_physical_samples'] - previous_physical == delta * 100,
                    'NN cadence/counter discontinuity')
        previous_nn, previous_physical = nn['completed_nn_steps'], nn['completed_physical_samples']
        for key in runtime_sets:
            runtime_sets[key].add(nn[key])
        provenance = frame['processor_provenance']
        require(provenance['overflowed_scope_samples'] == 0, 'Processor sample overflow')
        for boundary, counter in [('begin', begin_cpus), ('end', end_cpus)]:
            sample = provenance[boundary]
            require(sample['group'] == 0 and sample['logical_processor_index'] in range(8), 'GT outside selected class')
            counter[sample['logical_processor_index']] += 1
        for sample in provenance['phase_entry_processors']:
            require(sample['group'] == 0 and sample['logical_processor_index'] in range(8), 'Refresh entry outside selected class')
            refresh_cpus[sample['logical_processor_index']] += sample['refresh_bones']['calls']
        phases.update(frame['character_cpu_ms'])
    require(all(runtime_sets[key] == {'NNERuntimeORTCpu'} for key in ['run_runtime', 'walk_runtime', 'upper_runtime']),
            'Unexpected NN runtime')
    require(all(runtime_sets[key] == {100} for key in ['run_batch_size', 'walk_batch_size', 'upper_batch_size'])
            and runtime_sets['foot_roll_steps'] == {4}, 'Batch/foot-roll fidelity changed')
    require(sum(refresh_cpus.values()) == 36000, 'Incomplete Refresh processor samples')
    for key, value in phases.items():
        require(near(value / 360, validation['mean_character_cpu_ms'][key]), 'Phase mean differs: ' + key)

    require(validation['removed_during_bone_finalization'] and validation['removed_handles_rejected'] == 22
            and validation['survivor_handles_preserved'] == 2178, 'Removal callback/handles')
    require(len(validation['survivors_after_explicit_step']) == 99
            and all(row['success'] and row['validated_dynamic_rig_bodies'] == 22
                    and row['validated_skeleton_bones'] == 88 for row in validation['survivors_after_explicit_step']),
            'Survivor publication after removal')
    for boundary, steps in [('after_one_removed', 361), ('after_survivor_step', 362)]:
        state = validation[boundary]
        require(state['bodies'] == 2179 and state['constraints'] == 2079 and state['completed_steps'] == steps
                and not state['faulted'] and state['update_error_bits'] == 0, 'Removal lifecycle state')
    cancellation = validation['late_admission_cancellation']
    require(cancellation['success'] and cancellation['chaos_dynamic_bodies_while_pending'] == 22
            and cancellation['chaos_dynamic_bodies_after_cancellation'] == 0
            and cancellation['completion_callbacks_on_cancellation'] == 0
            and cancellation['survivor_body_states_unchanged'] == 2178
            and cancellation['repeated_pending_enable_idempotent'] and cancellation['pending_token_cleared']
            and cancellation['completion_delegate_cleared'], 'Pending cancellation lifecycle')
    require(validation['after_disable']['bodies'] == 1 and validation['after_disable']['constraints'] == 0
            and validation['after_disable']['active_bodies'] == 0 and not validation['after_disable']['faulted']
            and validation['coordinator_characters_after_disable'] == 0
            and validation['chaos_dynamic_bodies_after_disable'] == 0
            and validation['stale_handles_rejected'] == 2200 and validation['returned_kinematic'], 'Final teardown')
    control = report['game_thread_processor_control']
    require(control['requested'] and control['applied'] and control['restored'] and not control['restoration_pending']
            and control['selected_efficiency_class'] == 1
            and control['applied_game_thread_affinity']['mask_hex'] == '0xff'
            and control['restored_game_thread_affinity']['mask_hex'] == '0xfff'
            and control['process_affinity_unchanged_after_apply'], 'GT affinity control/restore')
    for boundary in ['initial_policy', 'final_policy']:
        policy = report['processor_environment'][boundary]
        require(policy['process_priority_class'] == 32 and policy['process_affinity_mask_hex'] == '0xfff',
                'Process policy changed')
    return {
        'report': str(path.relative_to(PROJECT)), 'sha256': digest, 'bytes': len(raw), 'verified': True,
        'padding_cm': padding, 'world_tick': case['world_tick'], 'warmup_frames': report['warmup_frames'],
        'sample_frames': len(frames), 'query_settings': snapshots[0]['runtime_cvars'],
        'native_skeletal_actor_buckets': case['after']['skeletal_actor_spatial_buckets'],
        'actual_nn': actual, 'runtime_values': {key: sorted(value) for key, value in runtime_sets.items()},
        'row_counts': dict(counts), 'capsule_filtered_agent_indices': sorted(fallback_agents),
        'capsule_filtered_frame_indices': sorted(fallback_frames), 'mean_character_cpu_ms': validation['mean_character_cpu_ms'],
        'synchronous_jolt_step_mean_ms': validation['mean_synchronous_jolt_step_ms'],
        'max_query_bone_position_cm': validation['max_query_bone_position_cm'],
        'max_query_bone_angle_degrees': validation['max_query_bone_angle_degrees'],
        'lifecycle_verified': True, 'removed_during_bone_finalization': validation['removed_during_bone_finalization'],
        'completed_pose_callback_invalidation': validation['completed_pose_callback_invalidation'],
        'late_admission_coverage_limit': cancellation['coverage_limit'],
        'next_frame_admission_exercised': cancellation['next_frame_admission_exercised'],
        'next_frame_cancellation_drain_exercised': cancellation['next_frame_cancellation_drain_exercised'],
        'external_post_endphysics_control_required': validation['external_post_endphysics_control_required'],
        'external_post_endphysics_control_test': validation['external_post_endphysics_control_test'],
        'motion_edge_evidence_present': validation['motion_edge_evidence_present'],
        'processor_samples': {'begin': dict(begin_cpus), 'end': dict(end_cpus), 'refresh_entry': dict(refresh_cpus)},
        'processor_control': control, 'processor_policy': report['processor_environment'],
        'render_scope': validation['render_scope'], 'contact_scope': validation['contact_scope'],
        'character_cpu_scope': validation['character_cpu_scope'], 'query_validation_scope': validation['query_validation_scope'],
    }


if __name__ == '__main__':
    rows = [audit(padding, name) for padding, name in FILES]
    result = {'all_three_verified': True, 'scope': 'Independent retained-report audit, not a new Unreal run or proof of repeat-run statistical significance.', 'runs': rows}
    output = Path(__file__).with_name('PaddingRunsAudit.json')
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'all_three_verified': True,
          'runs': [{'padding_cm': row['padding_cm'], 'world_mean_ms': row['world_tick']['mean_ms'],
                    'query_scene_mean_ms': row['mean_character_cpu_ms']['query_scene_update'],
                    'rows': row['row_counts']} for row in rows]}, indent=2))
