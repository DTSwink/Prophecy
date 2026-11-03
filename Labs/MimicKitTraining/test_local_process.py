"""Subprocess-level checks; no training, cloud API or simulation required."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from local_process import ServiceLock, stop_child_tree, is_current_run


class LocalProcessTests(unittest.TestCase):
    def test_handoff_only_retires_on_valid_different_run(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'active_run.json'
            self.assertTrue(is_current_run(folder,'current'))
            path.write_text('{')
            self.assertTrue(is_current_run(folder,'current'))
            path.write_text('{"run":"current"}')
            self.assertTrue(is_current_run(folder,'current'))
            path.write_text('{"run":"new"}')
            self.assertFalse(is_current_run(folder,'current'))

    def test_exclusive_and_released(self):
        with tempfile.TemporaryDirectory() as folder:
            lock=Path(folder)/'service.lock'
            code=('from local_process import ServiceLock; '
                  f'lock=ServiceLock({str(lock)!r}); lock.__enter__()')
            with ServiceLock(lock):
                child=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parent,
                                     capture_output=True,timeout=10)
                self.assertNotEqual(child.returncode,0)
                self.assertIn(b'Service already running',child.stderr)
            child=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parent,
                                 capture_output=True,timeout=10)
            self.assertEqual(child.returncode,0,child.stderr)
            # Process exit releases ownership too, even without __exit__.
            with ServiceLock(lock):pass

    def test_terminates_child_and_grandchild(self):
        import socket
        code=('import subprocess,sys,time; '
              'p=subprocess.Popen([sys.executable,"-u","-c",'
              '\'import socket,time; s=socket.socket(); s.bind(("127.0.0.1",0)); '
              's.listen(); print(s.getsockname()[1],flush=True); time.sleep(60)\']); '
              'time.sleep(60)')
        process=subprocess.Popen([sys.executable,'-u','-c',code],stdout=subprocess.PIPE,text=True)
        try:
            port=int(process.stdout.readline())
            with socket.create_connection(('127.0.0.1',port),timeout=2):pass
            stop_child_tree(process)
            with self.assertRaises(OSError):
                socket.create_connection(('127.0.0.1',port),timeout=2)
        finally:
            stop_child_tree(process)
            process.stdout.close()


if __name__=='__main__':unittest.main()
