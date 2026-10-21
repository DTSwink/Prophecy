"""CPU-only checks for equal transition budgets and separate evaluation worlds."""
import unittest
from types import SimpleNamespace

from loco_learning_sweep import (
    REFERENCE_TRANSITIONS, evaluation_pair, experiment_schedule, world_counts,
)


class SweepWorldsTest(unittest.TestCase):
    plan = dict(worlds=512, equivalent_updates=256, evaluate_at_updates=[0, 128, 256])

    def test_default_budget_unchanged(self):
        self.assertEqual(experiment_schedule({}, self.plan), (32, 256, {0: 0, 128: 128, 256: 256}))

    def test_large_training_batch_equal_transitions(self):
        ticks, budget, snapshots = experiment_schedule({'training_worlds': 1024}, self.plan)
        self.assertEqual(snapshots, {0: 0, 64: 128, 128: 256})
        actual_updates = budget * REFERENCE_TRANSITIONS // (1024 * ticks)
        self.assertEqual(actual_updates, 128)
        self.assertEqual(actual_updates * ticks * 1024, 256 * 32 * 512)

    def test_rollout_and_worlds_both_scale_budget(self):
        self.assertEqual(experiment_schedule({'training_worlds': 1024, 'steps_per_iter': 64}, self.plan),
                         (64, 256, {0: 0, 32: 128, 64: 256}))

    def test_no_partial_updates_or_changed_evaluation_worlds(self):
        with self.assertRaises(ValueError):
            experiment_schedule({'training_worlds': 1024, 'evaluate_at_updates': [1, 256]}, self.plan)
        with self.assertRaises(ValueError):
            world_counts({}, {'evaluation_worlds': 1024})
        with self.assertRaises(ValueError):
            world_counts({'training_worlds': 128}, self.plan)

    def test_default_keeps_same_objects_without_factory_calls(self):
        env, agent = object(), object()
        def forbidden(*args):
            raise AssertionError('Default evaluation must not construct another environment')
        actual = evaluation_pair(env, agent, 512, 512, forbidden, forbidden, forbidden)
        self.assertEqual(actual, (env, agent, False))

    def test_large_batch_constructs_separate_512_pair(self):
        training_env, training_agent = object(), object()
        calls = []
        def env_factory(worlds):
            calls.append(('env', worlds))
            return SimpleNamespace(worlds=worlds)
        def agent_factory(env):
            calls.append(('agent', env.worlds))
            return SimpleNamespace(env=env)
        def install(agent):
            calls.append(('privileged', agent.env.worlds))
            agent.installed = True
        env, agent, recreated = evaluation_pair(training_env, training_agent, 1024, 512,
                                                 env_factory, agent_factory, install)
        self.assertTrue(recreated)
        self.assertIsNot(env, training_env)
        self.assertIsNot(agent, training_agent)
        self.assertIs(agent.env, env)
        self.assertTrue(agent.installed)
        self.assertEqual(calls, [('env', 512), ('agent', 512), ('privileged', 512)])


if __name__ == '__main__':
    unittest.main()
