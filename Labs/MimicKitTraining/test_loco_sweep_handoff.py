"""CPU-only checks for the final sweep-queue handoff gate."""
import json
from pathlib import Path
import tempfile
import unittest

from loco_sweep_confirm import validate_handoff


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.previous = self.root / 'old'
        self.destination = self.root / 'new'
        self.previous.mkdir()
        self.destination.mkdir()
        self.write_state(active=None, finished=1000)

    def write_state(self, **state):
        (self.previous / 'queue_status.json').write_text(json.dumps(state))

    def check(self, now=1200):
        return validate_handoff(self.previous, self.destination, now=now)

    def test_finished_queue_has_sufficient_grace(self):
        self.assertEqual(self.check()['idle_seconds_left'], 100)

    def test_upload_delay_exhausting_grace_is_rejected(self):
        self.assertEqual(self.check(now=1270)['idle_seconds_left'], 30)
        with self.assertRaises(RuntimeError):
            self.check(now=1271)

    def test_existing_stop_handoff_or_destination_are_rejected(self):
        for marker in (self.previous / 'billing-stopped.json',
                       self.previous / 'next-stage-started',
                       self.destination / 'queue_status.json'):
            marker.write_text('{}')
            with self.assertRaises(RuntimeError):
                self.check()
            marker.unlink()

    def test_failed_cancelled_active_or_unfinished_are_rejected(self):
        for state in (dict(active='trial', finished=1000), dict(active=None),
                      dict(active=None, finished=1000, failed='trial error'),
                      dict(active=None, finished=1000, cancelled=True)):
            self.write_state(**state)
            with self.assertRaises(RuntimeError):
                self.check()

    def test_configured_idle_grace_is_respected(self):
        (self.previous / 'plan.json').write_text(json.dumps({'idle_stop_seconds': 120}))
        self.assertEqual(self.check(now=1080)['idle_seconds_left'], 40)
        with self.assertRaises(RuntimeError):
            self.check(now=1100)


if __name__ == '__main__':
    unittest.main()
