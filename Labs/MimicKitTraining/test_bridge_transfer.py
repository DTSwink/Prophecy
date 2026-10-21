"""Replay retries must never publish a tail fragment or discard a valid capture."""
import base64
import tempfile
import unittest
from pathlib import Path
from bridge import receive_file


def chunk(data, offset=0, complete=True):
    return dict(data=base64.b64encode(data).decode(), offset=offset, complete=complete)


class ReplayTransferTest(unittest.TestCase):
    def test_failed_conversion_preserves_previous_and_whole_retry_works(self):
        with tempfile.TemporaryDirectory() as directory:
            local=Path(directory)/'replay.npz'
            local.write_bytes(b'previous')
            receive_file(local,chunk(b'head',complete=False))
            def reject(path):
                raise ValueError('bad archive')
            with self.assertRaises(ValueError):
                receive_file(local,chunk(b'tail',4),reject)
            self.assertEqual(local.read_bytes(),b'previous')
            receive_file(local,chunk(b'new',complete=False))
            result=receive_file(local,chunk(b'archive',3),lambda path:path.read_bytes())
            self.assertEqual(result,b'newarchive')
            self.assertEqual(local.read_bytes(),b'newarchive')

    def test_missing_or_duplicate_chunk_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            local=Path(directory)/'replay.npz'
            with self.assertRaises(ValueError):
                receive_file(local,chunk(b'tail',4))
            receive_file(local,chunk(b'head',complete=False))
            receive_file(local,chunk(b'tail',4,False))
            with self.assertRaises(ValueError):
                receive_file(local,chunk(b'tail',4))
            self.assertFalse(local.exists())

    def test_new_version_discards_old_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            local=Path(directory)/'replay.npz'
            receive_file(local,chunk(b'oldpartial',complete=False))
            receive_file(local,chunk(b'new',complete=False))
            receive_file(local,chunk(b'version',3))
            self.assertEqual(local.read_bytes(),b'newversion')


if __name__=='__main__':
    unittest.main()
