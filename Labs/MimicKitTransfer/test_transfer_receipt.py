"""Reject reuse of native transfer evidence after the body export changes."""
import tempfile,unittest
from pathlib import Path
from verify_transfer import require_matching_body


class TransferBodyEvidenceTest(unittest.TestCase):
    def test_matching_and_changed_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            native=Path(folder)/'native';current=Path(folder)/'current'
            native.mkdir();current.mkdir()
            names=('humanoid_uefn.xml','limits.json','physics.json')
            for name in names:
                (native/name).write_bytes(b'original')
                (current/name).write_bytes(b'original')
            self.assertEqual(require_matching_body(native,current),[native/name for name in names])
            for name in names:
                with self.subTest(changed=name):
                    (current/name).write_bytes(b'updated')
                    with self.assertRaisesRegex(RuntimeError,name.replace('.',r'\.')):
                        require_matching_body(native,current)
                    (current/name).write_bytes(b'original')


if __name__=='__main__':unittest.main()
