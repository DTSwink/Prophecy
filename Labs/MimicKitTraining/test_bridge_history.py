import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from bridge import publish_rollout

class HistoryTests(unittest.TestCase):
    def test_preserves_each_capture_and_capture_time(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            for step in (100,200,300,300):
                payload=dict(step=step,computed_at=datetime.fromtimestamp(1700000000+step,timezone.utc).isoformat())
                publish_rollout(p,payload)
            self.assertEqual(len(list(p.glob('rollout_step_*.json'))),3)
            self.assertEqual(json.loads((p/'last_batch_rollout.json').read_text())['step'],300)
            for step in (100,200,300):
                f=p/f'rollout_step_{step:08d}.json'
                self.assertEqual(json.loads(f.read_text())['step'],step)
                self.assertAlmostEqual(f.stat().st_mtime,1700000000+step,places=3)

if __name__=='__main__':unittest.main()
