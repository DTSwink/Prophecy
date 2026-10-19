"""Multi-row replays larger than one transfer chunk must arrive intact."""
import base64
import gzip
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


class TelemetryTests(unittest.TestCase):
    def test_large_snapshot_and_replacement(self):
        source=Path(__file__).with_name('telemetry.py').read_text()
        with tempfile.TemporaryDirectory() as folder:
            code=source.replace("root=Path('/workspace/mimickit_trial/runs')/run",'root=Path('+repr(folder)+')')
            path=Path(folder)/'replay.npz';original=os.urandom(3*1024*1024);path.write_bytes(original)
            def request(seen):
                output=io.StringIO()
                with patch.object(sys,'argv',['telemetry.py','test']),patch.object(sys,'stdin',io.StringIO(json.dumps(seen)+'\n')),patch.object(sys,'stdout',output):
                    exec(compile(code,'telemetry.py','exec'),{})
                return json.loads(gzip.decompress(base64.b64decode(output.getvalue())))
            first=request({})['replay.npz'];self.assertFalse(first['complete'])
            data=base64.b64decode(first['data'])
            second=request({'replay.npz':dict(version=first['version'],size=len(data))})['replay.npz']
            self.assertTrue(second['complete']);self.assertEqual(second['offset'],len(data))
            self.assertEqual(data+base64.b64decode(second['data']),original)
            path.write_bytes(b'replacement')
            replaced=request({'replay.npz':dict(version=first['version'],size=len(data))})['replay.npz']
            self.assertEqual(replaced['offset'],0);self.assertEqual(base64.b64decode(replaced['data']),b'replacement')
            (Path(folder)/'status.json').write_text(json.dumps(dict(iteration=10,losses={'total':2.},
                evaluation=dict(mean_return=.5,replay=dict(samples=123,frame_phase=[0]*1000,replay_rows=[{},{}])))))
            status=request({})['status.json'];raw=base64.b64decode(status['data']);value=json.loads(raw)
            self.assertEqual(value['losses'],{'total':2.})
            self.assertEqual(value['evaluation']['replay'],dict(samples=123,row_count=2))
            self.assertNotIn('status.json',request({'status.json':dict(version=status['version'],size=len(raw))}))


if __name__=='__main__':unittest.main()
