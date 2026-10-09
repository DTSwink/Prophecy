"""Exercise the real UBT scheduler with harmless timed jobs, not game builds."""
import ctypes
import gc
import json
import os
import pathlib
import re
import subprocess
import sys
import time

if len(sys.argv) > 1 and sys.argv[1] == '--job':
    started = time.time()
    time.sleep(4)
    pathlib.Path(sys.argv[2]).write_text(json.dumps({'start': started, 'end': time.time()}))
    sys.exit(0)

class Memory(ctypes.Structure):
    _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
        (name, ctypes.c_ulonglong) for name in ('total', 'free', 'commit', 'free_commit', 'virtual', 'free_virtual', 'extended')]

state = Memory()
state.length = ctypes.sizeof(state)
assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state))
# Cross the one/two worker boundary without exhausting memory.
allocation_size = max(0, state.free - int(1.8 * 1024**3))
if not 2.3 * 1024**3 < state.free < 3.3 * 1024**3:
    raise SystemExit('Test requires 2.3-3.3 GiB free for the bounded 1 -> 2 worker check.')
project = pathlib.Path(__file__).resolve().parents[2]
output = project / 'Saved/Diagnostics/DynamicBuildWorkers' / time.strftime('%Y%m%d-%H%M%S')
output.mkdir(parents=True)
engine = pathlib.Path('C:/Program Files/Epic Games/UE_5.7')
actions = []
for index in range(6):
    produced = output / f'job{index}.json'
    actions.append(dict(Type='Compile', WorkingDirectory=str(output), CommandPath=sys.executable,
        CommandArguments=f'"{pathlib.Path(__file__).resolve()}" --job "{produced}"',
        CommandDescription='Dynamic RAM probe', StatusDescription=f'Job {index}',
        bCanExecuteInUBA=False, bCanExecuteRemotely=False, ProducedItems=[str(produced)],
        PrerequisiteItems=[str(output / 'job0.json')] if index else []))
actions_path = output / 'actions.json'
actions_path.write_text(json.dumps(dict(Environment={}, Actions=actions)))
allocation = bytearray(allocation_size)
started = time.time()
with (output / 'console.log').open('w') as log:
    process = subprocess.Popen([
        str(engine / 'Engine/Binaries/ThirdParty/DotNet/8.0.412/win-x64/dotnet.exe'),
        str(engine / 'Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.dll'),
        '-Mode=Execute', f'-Actions={actions_path}', f'-Project={project / "GameAnimationSample3.uproject"}',
        'GameAnimationSample3Editor', 'Win64', 'Development', f'-Log={output / "ubt.log"}'],
        stdout=log, stderr=subprocess.STDOUT,
        env={**os.environ, 'PROPHECY_BUILD_MEMORY_PER_ACTION_MB': '1024'})
    try:
        time.sleep(10)
        released = time.time()
        del allocation
        gc.collect()
        time.sleep(4)
        allocation = bytearray(allocation_size)
        pressure_restored = time.time()
        time.sleep(4)
        del allocation
        gc.collect()
        process.wait(timeout=35)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
jobs = [json.loads(path.read_text()) for path in sorted(output.glob('job*.json'))]
log = (output / 'console.log').read_text(errors='replace')
limits = [int(value) for value in re.findall(r'Worker ceiling (\d+)/', log)]
overlap = any(max(a['start'], b['start']) < min(a['end'], b['end']) and
    max(a['start'], b['start']) > released for i, a in enumerate(jobs) for b in jobs[i+1:])
passed = (process.returncode == 0 and len(jobs) == 6 and limits[0] == 1
    and max(limits) >= 2 and overlap and 1 in limits[limits.index(max(limits)) + 1:])
result = dict(passed=passed, allocation_bytes=allocation_size, started=started,
    released=released, pressure_restored=pressure_restored, limits=limits, jobs=jobs, exit_code=process.returncode)
(output / 'result.json').write_text(json.dumps(result, indent=2))
print(json.dumps({'output': str(output), **result}, indent=2))
print(log)
sys.exit(0 if passed else 1)
