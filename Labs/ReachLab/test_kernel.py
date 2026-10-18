"""Owned stdin/stdout native solver for numeric JS tests, no HTTP or rendering."""
import sys,json,importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('reach',Path(__file__).with_name('server.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
for line in sys.stdin:
 try:print(json.dumps(module.solve(json.loads(line))),flush=True)
 except Exception as e:print(json.dumps({'error':str(e)}),flush=True)
