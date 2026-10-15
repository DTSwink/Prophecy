"""Reloadable pod-scoped deadline; invalid reads retain the last bounded limit."""
import json
import math
import time
from pathlib import Path

class RuntimeDeadline:
    def __init__(self, path, pod_id, fallback, reserve=0, refresh_seconds=1):
        self.path = Path(path)
        self.pod_id = pod_id
        self.hard_stop = float(fallback)
        self.reserve = reserve
        self.refresh_seconds = refresh_seconds
        self.next_read = 0.

    def read(self, now=None):
        now = time.time() if now is None else now
        if now >= self.next_read:
            self.next_read = now + self.refresh_seconds
            try:
                value = json.loads(self.path.read_text())
                limit = float(value['hard_stop_unix'])
                if value['pod_id'] == self.pod_id and math.isfinite(limit) and limit > 0:
                    self.hard_stop = limit
            except (OSError, ValueError, KeyError, TypeError):
                pass
        return self.hard_stop - self.reserve
