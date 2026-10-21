"""CPU-only scheduling, saved counters and paired equal-time analysis checks."""
import copy
import math
import unittest

from loco_learning_sweep import experiment_schedule as original_schedule
from loco_learning_sweep_timed import TrainingSchedule, REFERENCE_TRANSITIONS
from analyze_loco_sweeps_timed import compare_endpoints, compare_timed, timed_endpoint


def simulate(spec, seconds, plan=None):
    schedule = TrainingSchedule(spec, plan or {})
    snapshots = [0] if 0 in schedule.evaluate_after else []
    while not schedule.stopped:
        decision = schedule.record_update(seconds)
        if decision['snapshot']:
            snapshots.append(decision['equivalent_updates'])
    return schedule, snapshots


class ScheduleTest(unittest.TestCase):
    def test_default_schedules_preserve_original_counts_and_snapshots(self):
        for spec in ({}, {'training_worlds': 1024}, {'steps_per_iter': 64},
                     {'training_worlds': 1024, 'steps_per_iter': 64}):
            plan = dict(equivalent_updates=256, evaluate_at_updates=[0, 128, 256])
            expected = original_schedule(spec, plan)
            schedule, snapshots = simulate(spec, 1.25, plan)
            self.assertEqual((schedule.ticks, schedule.minimum_equivalent_updates,
                              schedule.evaluate_after), expected)
            self.assertEqual(snapshots, [0, 128, 256])
            self.assertEqual(schedule.equivalent_updates, 256)
            self.assertIsNone(schedule.timed_snapshot)

    def test_time_crosses_before_minimum_but_training_continues_to_1024(self):
        schedule, snapshots = simulate({'timed_snapshot_seconds': 1800}, 2.)
        self.assertEqual(schedule.completed_updates, 1024)
        self.assertEqual(snapshots, [512, 900, 1024])
        self.assertEqual(schedule.timed_snapshot['actual_training_seconds'], 1800.)
        self.assertEqual(schedule.timed_snapshot['previous_training_seconds'], 1798.)
        self.assertEqual(schedule.training_seconds, 2048.)

    def test_time_crosses_after_minimum_and_stops_at_first_crossing(self):
        schedule, snapshots = simulate({'timed_snapshot_seconds': 1800}, 1.1)
        self.assertEqual(schedule.completed_updates, 1637)
        self.assertEqual(snapshots, [512, 1024, 1637])
        receipt = schedule.timed_snapshot
        self.assertLess(receipt['previous_training_seconds'], 1800)
        self.assertGreaterEqual(receipt['actual_training_seconds'], 1800)
        self.assertLess(receipt['overshoot_seconds'], 1.1)
        self.assertEqual(schedule.timing_metadata()['stop_reason'], 'minimum_updates_and_time_reached')

    def test_cap_does_not_invent_a_timed_snapshot(self):
        schedule, snapshots = simulate({'timed_snapshot_seconds': 1800}, .5)
        self.assertEqual(schedule.completed_updates, 2048)
        self.assertEqual(snapshots, [512, 1024])
        self.assertIsNone(schedule.timed_snapshot)
        self.assertFalse(schedule.timing_metadata()['reached'])
        self.assertEqual(schedule.timing_metadata()['stop_reason'], 'max_equivalent_updates')

    def test_coincident_fixed_and_timed_snapshot_is_saved_once(self):
        schedule, snapshots = simulate({'timed_snapshot_seconds': 1024}, 1.)
        self.assertEqual(snapshots, [512, 1024])
        self.assertEqual(schedule.timed_snapshot['equivalent_updates'], 1024)

    def test_wall_time_is_reported_separately_without_triggering_early_snapshot(self):
        schedule = TrainingSchedule({'timed_snapshot_seconds': 3}, {})
        schedule.record_update(2., training_wall_seconds=100.)
        self.assertIsNone(schedule.timed_snapshot)
        schedule.record_update(2., training_wall_seconds=200.)
        self.assertEqual(schedule.timed_snapshot['actual_training_seconds'], 4.)
        self.assertEqual(schedule.timed_snapshot['training_wall_seconds'], 200.)

    def test_actual_optimizer_updates_and_samples_for_scaled_rollout(self):
        schedule, snapshots = simulate(dict(timed_snapshot_seconds=1800,
            training_worlds=1024, steps_per_iter=64), 3.)
        self.assertEqual(schedule.completed_updates, 512)
        self.assertEqual(schedule.equivalent_updates, 2048)
        self.assertIsNone(schedule.timed_snapshot)
        self.assertEqual(snapshots, [512, 1024])
        counts = schedule.final_counts(1505624064, 91896)
        self.assertEqual(counts['completed_iteration'], 92407)
        self.assertEqual(counts['samples'], 1505624064 + 512 * 1024 * 64)
        self.assertEqual(counts['training_transitions'], 2048 * REFERENCE_TRANSITIONS)
        self.assertEqual(counts['actual_training_updates'], 512)

    def test_final_state_counts_are_actual_stop_not_planned_maximum(self):
        schedule, _ = simulate({'timed_snapshot_seconds': 1800}, 2.)
        counts = schedule.final_counts(1000, 50)
        self.assertEqual(schedule.maximum_updates, 2048)
        self.assertEqual(counts['actual_training_updates'], 1024)
        self.assertEqual(counts['samples'], 1000 + 1024 * REFERENCE_TRANSITIONS)
        self.assertEqual(counts['completed_iteration'], 1073)
        self.assertEqual(counts['training_seconds'], 2048)

    def test_zero_default_budget_and_invalid_timing_are_handled(self):
        schedule, snapshots = simulate({'equivalent_updates': 0}, 1.)
        self.assertEqual(snapshots, [0])
        self.assertEqual(schedule.final_counts(1000, 50)['completed_iteration'], 49)
        for target in (0, -1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                TrainingSchedule({'timed_snapshot_seconds': target}, {})
        with self.assertRaises(ValueError):
            TrainingSchedule({'timed_snapshot_seconds': 1800, 'max_equivalent_updates': 4096}, {})
        with self.assertRaises(ValueError):
            TrainingSchedule({'timed_snapshot_seconds': 1800, 'max_equivalent_updates': 1000}, {})
        schedule = TrainingSchedule({'equivalent_updates': 1}, {})
        for duration in (0, -1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                schedule.record_update(duration)
        schedule.record_update(1.)
        with self.assertRaises(RuntimeError):
            schedule.record_update(1.)


def fixture(name, seconds, perturbation_fails=True):
    schedule = TrainingSchedule({'timed_snapshot_seconds': 1800}, {})
    rows, snapshot_steps = [], []
    while not schedule.stopped:
        decision = schedule.record_update(seconds)
        rows.append(dict(update=schedule.completed_updates, equivalent_updates=schedule.equivalent_updates,
            seconds=seconds, transitions=schedule.completed_updates*REFERENCE_TRANSITIONS,
            metrics={'actor_learning_rate': schedule.completed_updates*1e-6}))
        if decision['snapshot']:
            snapshot_steps.append(decision['equivalent_updates'])
    hashes = {k: 'same_'+k for k in ('observation', 'position', 'velocity', 'target', 'motion', 'yaw')}
    evaluations = []
    for endpoint in snapshot_steps:
        for seed in range(8):
            evaluations.append(dict(evaluation_update=endpoint, seed=seed, rows=3, initial_hashes=hashes,
                group_labels={'0': 'normal_loco', '1': 'perturbed_loco', '2': 'normal_idle', '3': 'perturbed_idle'},
                row_ids=[0, 1, 2], motion_id=[0, 1, 2], group=[0, 1, 2], gait=[1, 1, -1], equipment=[0, 0, 0],
                initial_yaw_degrees=[0, 120, 0], final_done=[3, 1 if perturbation_fails else 3, 3],
                end_ticks=[300, 20 if perturbation_fails else 120, 300], episode_return=[1, 2, 3],
                mean_body_tracking_cost=[.1, .2, .1], mean_body_position_distance_m2=[.01, .02, .01],
                end_body_position_distance_m2=[.01, .02, .01]))
    return dict(variant=name, worlds=512, training_worlds=512, evaluation_worlds=3,
        training_seed=13579, training_initial_hashes=hashes, training_initial_hashes_worlds=512,
        checkpoint_sha256='same_checkpoint', environment_config_sha256='same_environment',
        motion_names=['normal', 'perturbed', 'idle'], updates=rows, evaluations=evaluations,
        evaluation_seeds=list(range(8)), timed_training=schedule.timing_metadata(),
        complete=True, failed=False)


class AnalysisTest(unittest.TestCase):
    def setUp(self):
        self.baseline = fixture('baseline', 2.)
        self.candidate = fixture('candidate', 1., perturbation_fails=False)

    def test_equal_time_uses_real_distinct_endpoints_and_correct_stats(self):
        original = copy.deepcopy(self.baseline)
        result = compare_timed(self.candidate, self.baseline, repetitions=20)
        self.assertTrue(result['paired_valid'], result['errors'])
        self.assertIsNone(result['equivalent_updates'])
        self.assertEqual(result['candidate_equivalent_updates'], 1800)
        self.assertEqual(result['baseline_equivalent_updates'], 900)
        self.assertEqual(result['candidate_training']['cumulative_update_seconds'], 1800)
        self.assertEqual(result['baseline_training']['cumulative_update_seconds'], 1800)
        self.assertEqual(result['candidate_training']['update_count'], 1800)
        self.assertEqual(result['baseline_training']['update_count'], 900)
        self.assertEqual(result['baseline_training']['transitions'], 900 * REFERENCE_TRANSITIONS)
        self.assertEqual(result['groups']['perturbed_loco']['failure_difference_pp'], -100)
        self.assertEqual(self.baseline, original)

    def test_explicit_endpoints_also_report_own_real_counts(self):
        result = compare_endpoints(self.candidate, self.baseline, 512, 1024, repetitions=20)
        self.assertTrue(result['paired_valid'], result['errors'])
        self.assertEqual(result['candidate_training']['cumulative_update_seconds'], 512)
        self.assertEqual(result['baseline_training']['cumulative_update_seconds'], 2048)
        self.assertFalse(result['interpolation_used'])

    def test_pairing_hash_checks_still_apply(self):
        changed = copy.deepcopy(self.candidate)
        for entry in changed['evaluations']:
            if entry['evaluation_update'] == 1800 and entry['seed'] == 0:
                entry['initial_hashes'] = dict(entry['initial_hashes'], yaw='different')
        result = compare_timed(changed, self.baseline, repetitions=20)
        self.assertFalse(result['paired_valid'])
        self.assertIn('seed 0: initial_hashes differ', result['errors'])

    def test_incomplete_or_failed_result_cannot_produce_paired_claim(self):
        for fields in (dict(complete=False), dict(failed=True)):
            changed = copy.deepcopy(self.candidate)
            changed.update(fields)
            result = compare_timed(changed, self.baseline, repetitions=20)
            self.assertFalse(result['paired_valid'])
            self.assertFalse(result['readiness']['ready'])
            self.assertEqual(result['groups'], {})

    def test_missing_endpoint_seed_is_not_treated_as_a_smaller_valid_comparison(self):
        changed = copy.deepcopy(self.candidate)
        changed['evaluations'] = [e for e in changed['evaluations']
            if not (e['evaluation_update'] == 1800 and e['seed'] == 7)]
        result = compare_timed(changed, self.baseline, repetitions=20)
        self.assertFalse(result['paired_valid'])
        self.assertEqual(result['readiness']['endpoint_details']['candidate']['missing_seeds'], [7])
        self.assertEqual(result['groups'], {})

    def test_unexpected_or_missing_planned_seed_set_is_rejected(self):
        for plan in (None, list(range(7)), [*range(8), 7], list(range(1, 9))):
            changed = copy.deepcopy(self.candidate)
            changed['evaluation_seeds'] = plan
            result = compare_timed(changed, self.baseline, repetitions=20)
            self.assertFalse(result['paired_valid'])
            self.assertEqual(result['groups'], {})

    def test_missing_or_incorrect_timed_receipts_are_rejected(self):
        changed = copy.deepcopy(self.baseline)
        changed['timed_training']['reached'] = False
        with self.assertRaises(ValueError):
            timed_endpoint(changed)
        for field, value in (('equivalent_updates', 1024), ('actual_training_seconds', 1900),
                             ('actual_training_updates', 1024), ('transitions', 1)):
            changed = copy.deepcopy(self.baseline)
            changed['timed_training']['snapshot'][field] = value
            with self.assertRaises(ValueError):
                timed_endpoint(changed)


if __name__ == '__main__':
    unittest.main()
