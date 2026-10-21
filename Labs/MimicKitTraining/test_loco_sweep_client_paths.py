"""Client-only path checks: emulate Windows while contacting no remote service."""
import contextlib
import io
import json
from pathlib import Path, PureWindowsPath
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import loco_sweep_confirm as controller


class ClientPathTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.local = self.root / 'loco-confirm'
        (self.local / 'base_config').mkdir(parents=True)
        (self.local / 'plan.json').write_text(json.dumps(dict(pod_id='test-owned-pod', queue_deadline_seconds=600)))
        for name in ('env', 'engine', 'agent'):
            (self.local / 'base_config' / (name + '_config.yaml')).write_text('{}')
        self.destinations, self.commands, self.sources = [], [], []
        def remote(code, **kwargs):
            self.sources.append(code)
            return json.dumps(dict(pid=12, started=1))
        cloud = SimpleNamespace(
            state=lambda: dict(pod_id='test-owned-pod', cost_per_hour=.59, connection={}),
            rp=SimpleNamespace(scp=lambda connection, source, destination, **kwargs:
                               self.destinations.append(destination)),
            ssh=lambda command: self.commands.append(command))
        self.shared = SimpleNamespace(OUT=self.root, ROOT=self.root, cloud=cloud, remote=remote)

    def test_launch_remote_paths_are_posix_when_client_uses_windows_paths(self):
        extension = ModuleType('extend_runtime')
        extension.extend = lambda value: value
        with patch.object(controller, 'RUNTIME', PureWindowsPath('/workspace/mimickit_trial')), \
             patch.object(controller, 'host', return_value=self.shared), \
             patch.dict(sys.modules, {'extend_runtime': extension}), \
             contextlib.redirect_stdout(io.StringIO()):
            controller.launch('loco-confirm', 'loco-sweeps')
        self.assertTrue(self.destinations)
        for value in self.destinations + self.commands + self.sources:
            self.assertNotIn('\\', value)
            self.assertIn('/workspace/mimickit_trial', value)
        self.assertTrue((self.local / 'launch.json').exists())

    def test_fetch_remote_path_is_posix_when_client_uses_windows_paths(self):
        self.shared.remote = lambda code, **kwargs: (self.sources.append(code) or '{}')
        with patch.object(controller, 'RUNTIME', PureWindowsPath('/workspace/mimickit_trial')), \
             patch.object(controller, 'host', return_value=self.shared), \
             contextlib.redirect_stdout(io.StringIO()):
            controller.fetch('loco-confirm')
        self.assertEqual(len(self.sources), 1)
        self.assertNotIn('\\', self.sources[0])
        self.assertIn('/workspace/mimickit_trial/loco-confirm', self.sources[0])


if __name__ == '__main__':
    unittest.main()
