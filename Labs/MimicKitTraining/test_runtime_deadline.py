import json
from pathlib import Path
import tempfile
import unittest
from runtime_deadline import RuntimeDeadline

class DeadlineTests(unittest.TestCase):
    def test_live_extension_preserves_instance(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'clock.json'
            clock=RuntimeDeadline(path,'owned',1000,reserve=165)
            self.assertEqual(clock.read(0),835)
            path.write_text(json.dumps(dict(pod_id='owned',hard_stop_unix=2000)))
            self.assertEqual(clock.read(2),1835)
            self.assertGreater(clock.read(1001),1001)
            self.assertLess(clock.read(1836),1836)

    def test_bad_or_other_pod_does_not_erase_limit(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'clock.json'
            clock=RuntimeDeadline(path,'owned',1000,refresh_seconds=0)
            for value in ['{',json.dumps(dict(pod_id='other',hard_stop_unix=9000)),
                          json.dumps(dict(pod_id='owned',hard_stop_unix=float('nan'))),
                          json.dumps(dict(pod_id='owned',hard_stop_unix=-1))]:
                path.write_text(value)
                self.assertEqual(clock.read(0),1000)

    def test_trainer_and_guard_share_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'clock.json'
            trainer=RuntimeDeadline(path,'owned',1000,165,0)
            guard=RuntimeDeadline(path,'owned',1000,0,0)
            viewer=RuntimeDeadline(path,'owned',1000,-180,0)
            for limit in [1000,2000,1500,253402300799]:
                path.write_text(json.dumps(dict(pod_id='owned',hard_stop_unix=limit)))
                self.assertEqual(guard.read(0)-trainer.read(0),165)
                self.assertEqual(viewer.read(0)-guard.read(0),180)

if __name__=='__main__':unittest.main()
