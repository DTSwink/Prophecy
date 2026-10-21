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
import zipfile
from pathlib import Path

import cloud
from extend_runtime import extend
from uefn_package import runtime_files


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
    parser.add_argument('--source-package', type=Path, help='Resume the exact previously verified source archive')
    parser.add_argument('--source-sha256', help='Required expected digest for source-package')
    parser.add_argument('training_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.seconds > 180
    argv = args.training_args
    if argv[:1] == ['--']: argv = argv[1:]
    assert '--name' in argv, 'Give each restart a new run name'
    name = argv[argv.index('--name') + 1]
    assert name and all(c.isalnum() or c in '_-' for c in name)
    preflight = IDLE_CHECK + '\nassert not (r/"runs"/NAME).exists()\n'.replace('NAME', repr(name))
    if '--omni-run-lr' in argv or '--equipment-omni' in argv:
        root=Path(__file__).resolve().parents[2]
        current={entry:hashlib.sha256(path.read_bytes()).hexdigest() for entry,path in runtime_files(root).items()}
        if args.source_package:
            assert args.source_sha256 and hashlib.sha256(args.source_package.read_bytes()).hexdigest()==args.source_sha256
            with zipfile.ZipFile(args.source_package) as package:
                current={entry:hashlib.sha256(package.read(entry)).hexdigest() for entry in current}
        preflight+='\nimport hashlib\nfor entry,digest in '+repr(current)+'.items():\n    assert hashlib.sha256((r/entry).read_bytes()).hexdigest()==digest, "Stale UEFN runtime; deploy current source before training: "+entry\n'
    cloud.ssh('python -c ' + shlex.quote(preflight))
    for helper in ('billing_stop.py','failure_stop.py'):
        cloud.rp.scp(cloud.state()['connection'],Path(__file__).with_name(helper),
                     '/workspace/mimickit_trial/pipeline/'+helper,timeout=45)
    if not args.keep_deadline:
        extend(time.time() + args.seconds)
    code = preflight + """
import subprocess,json,time
cmd=[str(r/'venv/bin/python'),'-u',str(r/'pipeline/train.py')]+ARGV
with open(r/(NAME+'.log'),'ab',buffering=0) as log:
    p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt=dict(pid=p.pid,name=NAME,launched_unix=time.time(),command=cmd)
(r/(NAME+'-launch.json')).write_text(json.dumps(receipt,indent=2))
with open(r/(NAME+'-exit-guard.log'),'ab',buffering=0) as log:
    guard=subprocess.Popen([str(r/'venv/bin/python'),str(r/'pipeline/failure_stop.py'),NAME],
        stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
receipt['exit_guard_pid']=guard.pid
(r/(NAME+'-launch.json')).write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
""".replace('ARGV', repr(argv)).replace('NAME', repr(name))
    receipt = json.loads(cloud.ssh('python -c ' + shlex.quote(code)))
    (cloud.OUT / (name + '-launch.json')).write_text(json.dumps(receipt, indent=2))
    active=cloud.OUT/'active_run.json'
    temporary=active.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(run=name,pod=cloud.state()['pod_id'],**receipt)))
    temporary.replace(active)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
