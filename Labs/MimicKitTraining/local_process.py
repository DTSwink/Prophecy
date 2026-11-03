"""Local-only service ownership. No provider or training control operations."""
import os
import json
import subprocess
from pathlib import Path


def is_current_run(state_dir, name):
    """Only a valid handoff to a different run retires an observer."""
    try:
        active = json.loads((Path(state_dir)/'active_run.json').read_text())
        return active.get('run') in (None, name)
    except (OSError, ValueError):
        return True  # A transient/partial handoff write must not kill telemetry.


class ServiceLock:
    """OS-released lock: one worker per service/scope, including manual launches."""
    def __init__(self, path):
        self.path = Path(path)
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open('a+b')
        self.stream.seek(0, 2)
        if not self.stream.tell():
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError(f'Service already running: {self.path}') from None
        return self

    def __exit__(self, *args):
        self.stream.close()


def stop_child_tree(process):
    """Popen owns this child; on Windows python.exe may only be a launcher."""
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       capture_output=True, check=False, timeout=20,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        process.terminate()
    process.wait(timeout=20)
