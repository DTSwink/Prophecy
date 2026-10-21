"""CPU-only checks for runner selection and bounded timed-run queue estimates."""
import math
import unittest

from loco_sweep_confirm import estimate_timeout, runner_script, validate_schedule


class ConfirmationTest(unittest.TestCase):
    def test_runner_selection_is_explicit_and_allowlisted(self):
        self.assertEqual(runner_script({}), 'loco_learning_sweep.py')
        self.assertEqual(runner_script({'runner_script': 'loco_learning_sweep_timed.py'}),
                         'loco_learning_sweep_timed.py')
        for value in ('../other.py', 'other.py', '/tmp/runner.py', None):
            with self.assertRaises(ValueError):
                runner_script({'runner_script': value})

    def test_default_schedule_and_timeouts_are_unchanged(self):
        plan = dict(equivalent_updates=256, variants={'baseline': {}})
        self.assertEqual(validate_schedule({}, plan), (32, 256, {256: 256}))
        expected = math.ceil((1.5 * 256 * 2.5 + 240 + 300) / 60) * 60
        self.assertEqual(estimate_timeout(plan, []), {'baseline': expected})
        plan['equivalent_updates'] = 1024
        expected = math.ceil((1.5 * 1024 * 2.5 + 240 + 300) / 60) * 60
        self.assertEqual(estimate_timeout(plan, []), {'baseline': expected})

    def test_timed_schedule_is_validated_before_launch(self):
        plan = dict(runner_script='loco_learning_sweep_timed.py', timed_snapshot_seconds=1800)
        schedule = validate_schedule({'training_worlds': 1024}, plan)
        self.assertEqual(schedule.minimum_updates, 512)
        self.assertEqual(schedule.maximum_updates, 1024)
        self.assertEqual(schedule.evaluate_after, {256: 512, 512: 1024})
        for spec in ({'timed_snapshot_seconds': -1}, {'max_equivalent_updates': 1000},
                     {'max_equivalent_updates': 4096}):
            with self.assertRaises(ValueError):
                validate_schedule(spec, plan)

    def test_timed_estimate_includes_target_and_three_or_four_evaluations(self):
        observed = [dict(equivalent_update_budget=256, training_wall_seconds=256,
                         training_seconds=256, evaluation_seconds=500,
                         evaluations=[{'evaluation_update': 256}])]
        plan = dict(runner_script='loco_learning_sweep_timed.py', timed_snapshot_seconds=1800,
                    equivalent_updates=1024, variants={'baseline': {}})
        expected = math.ceil((1.5 * 1801 + 3 * 500 + 300) / 60) * 60
        self.assertEqual(estimate_timeout(plan, observed), {'baseline': expected})
        plan['evaluate_at_updates'] = [0, 512, 1024]
        expected = math.ceil((1.5 * 1801 + 4 * 500 + 300) / 60) * 60
        self.assertEqual(estimate_timeout(plan, observed), {'baseline': expected})

    def test_timed_estimate_accounts_for_diagnostics_and_actual_prior_updates(self):
        observed = [dict(equivalent_update_budget=1024, actual_equivalent_updates=1800,
                         training_wall_seconds=1980, training_seconds=1800,
                         evaluation_seconds=500, evaluations=[{'evaluation_update': 1800}])]
        plan = dict(runner_script='loco_learning_sweep_timed.py', timed_snapshot_seconds=1800,
                    equivalent_updates=1024, variants={'worlds1024': {'training_worlds': 1024}})
        expected = math.ceil((1.5 * (1800 * 1.1 + 2 * 1.1) + 3 * 500 + 300) / 60) * 60
        self.assertEqual(estimate_timeout(plan, observed), {'worlds1024': expected})


if __name__ == '__main__':
    unittest.main()
