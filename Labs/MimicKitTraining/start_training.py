"""Launch a user-requested restart with a fresh hour on the existing owned pod.

Usage: python start_training.py -- --name NEW_NAME --task neutral_pose ...
Use --keep-deadline only for an administrative checkpoint reload, not a user restart.
Does not allocate a pod, stop an existing trainer, or change learning settings.
"""
import argparse
import json
import shlex
import time
import hashlib
from pathlib import Path

import cloud
from extend_runtime import extend


IDLE_CHECK = """from pathlib import Path
r=Path('/workspace/mimickit_trial')
assert not (r/'stop.request').exists(), 'Explicit stop request still present'
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit(): continue
    try: args=(proc/'cmdline').read_bytes().split(b'\\0')
    except OSError: continue
    assert b'/workspace/mimickit_trial/pipeline/train.py' not in args, 'Trainer already running'
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keep-deadline', action='store_true')
    parser.add_argument('--seconds', type=int, default=3600, help='User-authorized runtime from launch')
    parser.add_argument('training_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.seconds > 180
    argv = args.training_args
    if argv[:1] == ['--']: argv = argv[1:]
    assert '--name' in argv, 'Give each restart a new run name'
    name = argv[argv.index('--name') + 1]
    assert name and all(c.isalnum() or c in '_-' for c in name)
    preflight = IDLE_CHECK + '\nassert not (r/"runs"/NAME).exists()\n'.replace('NAME', repr(name))
    if '--omni-run-lr' in argv:
        root=Path(__file__).resolve().parents[2]
        current={entry:hashlib.sha256(path.read_bytes()).hexdigest() for entry,path in (
            ('assets/uefn/velocity_motors.py',root/'Labs/MimicKitUEFN/velocity_motors.py'),
            ('assets/uefn/body_velocity.py',root/'Labs/MimicKitUEFN/body_velocity.py'),
            ('pipeline/uefn_engine.py',Path(__file__).with_name('uefn_engine.py')),
            ('pipeline/train.py',Path(__file__).with_name('train.py')),
            ('pipeline/omni_config.py',Path(__file__).with_name('omni_config.py')))}
        preflight+='\nimport hashlib\nfor entry,digest in '+repr(current)+'.items():\n    assert hashlib.sha256((r/entry).read_bytes()).hexdigest()==digest, "Stale UEFN runtime; deploy current source before training: "+entry\n'
    cloud.ssh('python -c ' + shlex.quote(preflight))
    if not args.keep_deadline:
        extend(time.time() + args.seconds)
    code = preflight + """
import subprocess,json,time
cmd=[str(r/'venv/bin/python'),'-u',str(r/'pipeline/train.py')]+ARGV
with open(r/(NAME+'.log'),'ab',buffering=0) as log:
    p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt=dict(pid=p.pid,name=NAME,launched_unix=time.time(),command=cmd)
(r/(NAME+'-launch.json')).write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
""".replace('ARGV', repr(argv)).replace('NAME', repr(name))
    receipt = json.loads(cloud.ssh('python -c ' + shlex.quote(code)))
    (cloud.OUT / (name + '-launch.json')).write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
