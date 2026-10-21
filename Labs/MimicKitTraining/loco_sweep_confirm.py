"""Prepare/launch/fetch a separate confirmation queue on the owned sweep GPU.

Local prepare is read-only with respect to GPU and all production state:
  python loco_sweep_confirm.py prepare PLAN.json --directory loco-confirm
Launch only after the screen queue has finished, during its idle grace:
  python loco_sweep_confirm.py launch --directory loco-confirm
Fetch results, then preserve selected full optimizer-state artifacts locally:
  python loco_sweep_confirm.py fetch --directory loco-confirm
  python loco_sweep_confirm.py preserve --directory loco-confirm --variants baseline lr2

The remote queue stores results AND full training states in verified persistent
storage before marking a candidate backed up. Its deadline/idle-stop controls are
independent from the earlier queue, and never alter the production run pointers.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time


RUNTIME = Path('/workspace/mimickit_trial')
BUCKET = 'aj7d2jzwuq'
BACKUP_PREFIX = 'mimickit/pipeline_20261014/locomotion-sweeps-20261021'
RUNNER_SCRIPTS = ('loco_learning_sweep.py', 'loco_learning_sweep_timed.py')


def runner_script(plan):
    selected = plan.get('runner_script', RUNNER_SCRIPTS[0])
    if selected not in RUNNER_SCRIPTS:
        raise ValueError('runner_script must name an allowlisted isolated sweep runner')
    return selected


def validate_schedule(spec, plan):
    if runner_script(plan) == 'loco_learning_sweep_timed.py':
        from loco_learning_sweep_timed import TrainingSchedule
        return TrainingSchedule(spec, plan)
    from loco_learning_sweep import experiment_schedule
    return experiment_schedule(spec, plan)


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False))
    temporary.replace(path)


def safe_name(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}', value):
        raise ValueError('Use a simple alphanumeric directory/variant name, with _ or -')
    return value


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def validate_handoff(previous, destination, now=None, minimum_remaining_seconds=30):
    """Recheck immediately before spawn; uploads may have consumed idle grace."""
    previous, destination = Path(previous), Path(destination)
    state = json.loads((previous / 'queue_status.json').read_text())
    if state.get('active') or not state.get('finished') or state.get('failed') or state.get('cancelled'):
        raise RuntimeError('Previous queue must still be successfully finished')
    if (previous / 'billing-stopped.json').exists():
        raise RuntimeError('Previous queue has already stopped billing')
    if (previous / 'next-stage-started').exists():
        raise RuntimeError('Previous queue already handed off to a successor')
    if (destination / 'queue_status.json').exists():
        raise RuntimeError('Destination queue already exists')
    previous_plan_path = previous / 'plan.json'
    previous_plan = json.loads(previous_plan_path.read_text()) if previous_plan_path.exists() else {}
    idle_seconds = float(previous_plan.get('idle_stop_seconds', 300))
    remaining = float(state['finished']) + idle_seconds - (time.time() if now is None else now)
    if remaining < minimum_remaining_seconds:
        raise RuntimeError('Insufficient previous-queue idle grace for a safe handoff')
    return dict(previous_finished=state['finished'], idle_seconds_left=remaining)


def host():
    # Import sets MIMICKIT_STATE_DIR to the isolated sweep allocation. It does
    # not allocate/start/stop anything; production cloud state is never selected.
    import loco_sweep_cloud
    return loco_sweep_cloud


def estimate_timeout(plan, screening_results):
    """Budget wall time, including diagnostics, evaluation and cold setup."""
    per_update = []
    evaluation_seconds = []
    diagnostic_wall_ratios = []
    for value in screening_results:
        equivalent = value.get('actual_equivalent_updates', value.get('equivalent_update_budget', 0))
        elapsed = value.get('training_wall_seconds', value.get('training_seconds', 0))
        if equivalent and elapsed:
            per_update.append(float(elapsed) / equivalent)
        if elapsed and value.get('training_seconds'):
            diagnostic_wall_ratios.append(max(1., float(elapsed) / value['training_seconds']))
        if value.get('evaluation_seconds'):
            snapshots = len(set(e['evaluation_update'] for e in value.get('evaluations', []))) or 1
            evaluation_seconds.append(float(value['evaluation_seconds']) / snapshots)
    # Conservative fallback if no finished screen has been downloaded yet.
    seconds_per_reference_update = max(per_update, default=2.5)
    seconds_per_evaluation = max(evaluation_seconds, default=240.)
    estimates = {}
    selected_runner = runner_script(plan)
    for name, variant in plan['variants'].items():
        equivalent = int(variant.get('equivalent_updates', plan.get('equivalent_updates', 1024)))
        evaluations = variant.get('evaluate_at_updates', plan.get('evaluate_at_updates', [equivalent]))
        snapshots = len(set([*evaluations, equivalent]))
        training_wall = equivalent * seconds_per_reference_update
        if selected_runner == 'loco_learning_sweep_timed.py':
            schedule = validate_schedule(variant, plan)
            equivalent = schedule.minimum_equivalent_updates
            snapshots = len(schedule.evaluate_after)
            training_wall = equivalent * seconds_per_reference_update
            if schedule.target_seconds is not None:
                # Fixed512/1024 checkpoints plus a possibly distinct timed
                # checkpoint; an explicit initial checkpoint makes four.
                snapshots += 1
                actual_update_equivalents = schedule.transitions_per_update / 16384
                timed_wall = (schedule.target_seconds * max(diagnostic_wall_ratios, default=1.15)
                              + actual_update_equivalents * seconds_per_reference_update)
                training_wall = min(schedule.maximum_equivalent_updates * seconds_per_reference_update,
                                    max(training_wall, timed_wall))
        estimated = 1.5 * training_wall + snapshots * seconds_per_evaluation + 300
        minimum = max(900, int(math.ceil(equivalent * (3600 / 1024) / 60) * 60))
        estimates[name] = max(minimum, int(math.ceil(estimated / 60) * 60))
    return estimates


def prepare(plan_path, directory):
    shared = host()
    directory = safe_name(directory)
    destination = shared.OUT / directory
    if destination.exists() and (destination / 'launch.json').exists():
        raise RuntimeError('This confirmation directory was already launched; use a new name')
    requested = json.loads(Path(plan_path).read_text())
    requested.setdefault('equivalent_updates', 1024)
    original = json.loads((shared.OUT / 'plan.json').read_text())
    protected = json.loads((shared.OUT / 'protected-main-files.json').read_text())
    for filename, sha in protected.items():
        if digest(filename) != sha:
            raise RuntimeError('Protected production file changed since the screen: ' + filename)
    if requested.get('sha256', original['sha256']) != original['sha256']:
        raise ValueError('Confirmation must start from the same protected checkpoint')
    variants = requested.get('variants', {})
    if not variants:
        raise ValueError('Provide one or more explicitly named variants')
    for name, spec in variants.items():
        safe_name(name)
        validate_schedule(spec, requested)
    plan = dict(requested)
    plan.update(stage='confirmation', directory=directory, sha256=original['sha256'],
                checkpoint=original['checkpoint'], source=original['source'],
                worlds=int(requested.get('worlds', original.get('worlds', 512))),
                evaluation_seeds=requested.get('evaluation_seeds', original['evaluation_seeds']),
                pod_id=shared.cloud.state()['pod_id'], protected_main=protected,
                s3_prefix=BACKUP_PREFIX + '/' + directory,
                full_training_state_backups=True)
    results = [json.loads(p.read_text()) for p in shared.OUT.glob('result_*.json')]
    estimates = estimate_timeout(plan, results)
    requested_timeout = int(plan.get('variant_timeout_seconds', 0))
    plan['variant_timeouts'] = {name: max(requested_timeout, estimate)
                                for name, estimate in estimates.items()}
    plan['variant_timeout_seconds'] = max(plan['variant_timeouts'].values())
    plan['queue_deadline_seconds'] = sum(plan['variant_timeouts'].values()) + 600
    plan['timeout_basis'] = dict(estimated_variant_seconds=estimates,
        includes='1.5x observed training wall time, snapshot evaluations and five-minute cold-start allowance',
        minimum_variant_seconds='900 for up to256 equivalent updates; proportional thereafter,3600 at1024')
    if runner_script(plan) == 'loco_learning_sweep_timed.py':
        plan['timeout_basis']['includes'] = ('1.5x the larger of minimum-update training or timed target '
            'adjusted for observed diagnostic overhead, bounded by the maximum updates; '
            'fixed plus timed snapshot evaluations and five-minute cold-start allowance')
    plan.setdefault('idle_stop_seconds', 300)
    destination.mkdir(parents=True, exist_ok=True)
    configs = destination / 'base_config'
    configs.mkdir(exist_ok=True)
    for filename in ('env_config.yaml', 'engine_config.yaml', 'agent_config.yaml'):
        shutil.copyfile(shared.OUT / 'base_config' / filename, configs / filename)
    atomic_json(destination / 'plan.json', plan)
    print(json.dumps(dict(prepared=str(destination), variants=list(variants),
        timeouts=plan['variant_timeouts'], deadline_seconds=plan['queue_deadline_seconds'],
        gpu_unchanged=True)))


def launch(directory, previous_directory):
    shared = host()
    directory, previous_directory = safe_name(directory), safe_name(previous_directory)
    local = shared.OUT / directory
    plan = json.loads((local / 'plan.json').read_text())
    runner_script(plan)
    current = shared.cloud.state()
    if current['pod_id'] != plan['pod_id']:
        raise RuntimeError('Prepared confirmation belongs to a different sweep pod')
    if float(current['cost_per_hour']) > .59:
        raise RuntimeError('Sweep GPU exceeds the approved hourly ceiling')
    remote_dir = (RUNTIME / directory).as_posix()
    previous_dir = (RUNTIME / previous_directory).as_posix()
    check = shared.remote("""import json,time
from pathlib import Path
o=Path(PREVIOUS);s=json.loads((o/'queue_status.json').read_text())
if s.get('active') or not s.get('finished') or s.get('failed'):raise RuntimeError('Previous queue must finish successfully first')
if (o/'billing-stopped.json').exists():raise RuntimeError('Previous queue has already stopped billing')
if (o/'next-stage-started').exists():raise RuntimeError('Previous queue already handed off to a successor')
if time.time()>s['finished']+240:raise RuntimeError('Too close to previous queue idle stop; do not race its guard')
if (Path(DEST)/'queue_status.json').exists():raise RuntimeError('Destination queue already exists')
print(json.dumps({'previous_finished':s['finished'],'idle_seconds_left':s['finished']+300-time.time()}))
""".replace('PREVIOUS', repr(previous_dir)).replace('DEST', repr(remote_dir)))
    print(check)
    connection = current['connection']
    for filename in ('loco_learning_sweep.py', 'loco_learning_sweep_timed.py', 'loco_sweep_queue.py',
                     'loco_privileged_critic.py', 'loco_advantage_diagnostics.py',
                     'loco_sweep_confirm.py'):
        shared.cloud.rp.scp(connection, shared.ROOT / 'Labs/MimicKitTraining' / filename,
                            (RUNTIME / 'pipeline' / filename).as_posix(), timeout=45)
    shared.cloud.ssh('mkdir -p ' + remote_dir + '/base_config')
    shared.cloud.rp.scp(connection, local / 'plan.json', remote_dir + '/plan.json', timeout=45)
    for path in (local / 'base_config').glob('*.yaml'):
        shared.cloud.rp.scp(connection, path, remote_dir + '/base_config/' + path.name, timeout=45)
    from extend_runtime import extend
    deadline = extend(time.time() + plan['queue_deadline_seconds'])
    code = """import hashlib,json,os,subprocess,sys,time
from pathlib import Path
r=Path('/workspace/mimickit_trial');o=Path(DEST);previous=Path(PREVIOUS)
sys.path.insert(0,str(r/'pipeline'))
from loco_sweep_confirm import validate_handoff
plan=json.loads((o/'plan.json').read_text())
source=r/'loco-sweeps/checkpoint.zip';dest=o/'checkpoint.zip'
if hashlib.sha256(source.read_bytes()).hexdigest()!=plan['sha256']:raise RuntimeError('Source checkpoint changed')
if not dest.exists():os.link(source,dest)
if hashlib.sha256(dest.read_bytes()).hexdigest()!=plan['sha256']:raise RuntimeError('Destination checkpoint mismatch')
validate_handoff(previous,o,minimum_remaining_seconds=30)
with (o/'queue.log').open('ab') as log:
 proc=subprocess.Popen([str(r/'venv/bin/python'),'-u',str(r/'pipeline/loco_sweep_confirm.py'),'queue',str(o)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
deadline=time.time()+20
while time.time()<deadline:
 if proc.poll() is not None:raise RuntimeError('Confirmation queue exited during launch')
 if (o/'queue_status.json').exists():
  ready=json.loads((o/'queue_status.json').read_text())
  if ready.get('failed'):raise RuntimeError('Confirmation queue failed during launch')
  if ready.get('started'):break
 time.sleep(.25)
else:raise RuntimeError('Confirmation queue did not become ready')
# This marker transfers responsibility only after the successor is running.
receipt={'pid':proc.pid,'directory':str(o),'pod_id':plan['pod_id'],'started':time.time()}
tmp=previous/'next-stage-started.tmp';tmp.write_text(json.dumps(receipt));tmp.replace(previous/'next-stage-started')
print(json.dumps(receipt))
""".replace('DEST', repr(remote_dir)).replace('PREVIOUS', repr(previous_dir))
    receipt = json.loads(shared.remote(code, timeout=45))
    receipt['deadline'] = deadline
    atomic_json(local / 'launch.json', receipt)
    print(json.dumps(receipt))


def fetch(directory):
    shared = host()
    directory = safe_name(directory)
    local = shared.OUT / directory
    local.mkdir(exist_ok=True)
    try:
        raw = shared.remote("""import json
from pathlib import Path
o=Path(DIRECTORY)
files=[o/'queue_status.json',o/'artifact_backups.json',*o.glob('result_*.json')]
print(json.dumps({p.name:json.loads(p.read_text()) for p in files if p.exists()}))
""".replace('DIRECTORY', repr((RUNTIME / directory).as_posix())), timeout=60)
        values = json.loads(raw)
        source = 'live_gpu'
    except Exception:
        # Confirmation is deliberately allowed to stop its own GPU. Its small
        # manifest/results remain retrievable independently of retained-host capacity.
        client = shared.cloud.s3()
        prefix = BACKUP_PREFIX + '/' + directory
        def get_json(key):
            return json.loads(client.get_object(Bucket=BUCKET, Key=key)['Body'].read())
        manifest = get_json(prefix + '/artifact_backups.json')
        values = {'artifact_backups.json': manifest}
        for name, item in manifest.items():
            values['result_' + name + '.json'] = get_json(item['result']['key'])
        try:
            values['queue_status.json'] = get_json(prefix + '/queue_status.json')
        except Exception:
            values['queue_status.json'] = dict(stage='confirmation', completed=list(manifest),
                final_status_unavailable=True)
        source = 'persistent_storage'
    for filename, value in values.items():
        atomic_json(local / filename, value)
    print(json.dumps(dict(directory=directory, source=source, queue=values.get('queue_status.json'),
                         artifacts=list(values.get('artifact_backups.json', {})))))


def preserve(directory, variants):
    shared = host()
    directory = safe_name(directory)
    local = shared.OUT / directory
    manifest_path = local / 'artifact_backups.json'
    if not manifest_path.exists():
        raise RuntimeError('Fetch artifact_backups.json first, or recover it from the stage S3 prefix')
    manifest = json.loads(manifest_path.read_text())
    selected = variants or list(manifest)
    for name in selected:
        safe_name(name)
        if name not in manifest:
            raise ValueError('No verified backup for variant ' + name)
    client = shared.cloud.s3()
    preserved = {}
    for name in selected:
        item = manifest[name]['training_final_state']
        path = local / name / 'training_final_state.pt'
        path.parent.mkdir(exist_ok=True)
        if not path.exists() or digest(path) != item['sha256']:
            temporary = path.with_suffix('.part')
            client.download_file(BUCKET, item['key'], str(temporary))
            if digest(temporary) != item['sha256']:
                raise RuntimeError('Downloaded full state checksum mismatch: ' + name)
            temporary.replace(path)
        preserved[name] = dict(item, local=str(path), local_sha256_verified=True,
                               downloaded_unix=time.time())
    atomic_json(local / 'preserved-training-states.json', preserved)
    print(json.dumps(preserved, indent=2))


def remote_queue(directory):
    """Remote-only: serial candidates, per-variant timeout and verified backups."""
    sys.path.insert(0, str(RUNTIME / 'pipeline'))
    import boto3
    import torch
    from backup import verified_readback
    from billing_stop import stop_and_confirm
    out = Path(directory).resolve()
    if out.parent != RUNTIME:
        raise ValueError('Confirmation output must be a direct runtime child')
    plan = json.loads((out / 'plan.json').read_text())
    private = json.loads((RUNTIME / 'private.json').read_text())
    if private['pod_id'] != plan['pod_id']:
        raise RuntimeError('Confirmation pod identity mismatch')
    state = dict(started=time.time(), queue=list(plan['variants']), completed=[], active=None,
                 stage='confirmation', pid=os.getpid(), pod_id=plan['pod_id'])
    manifest = {}
    client = boto3.client('s3', **private['s3'])

    def save():
        state['updated_unix'] = time.time()
        atomic_json(out / 'queue_status.json', state)

    def stop(reason):
        stop_and_confirm(plan['pod_id'], private['runpod_api_key'], out / 'billing-stopped.json', reason)

    def upload(path, key):
        sha = digest(path)
        client.upload_file(str(path), BUCKET, key)
        verified_readback(client, BUCKET, key, sha)
        return dict(key=key, sha256=sha, bytes=path.stat().st_size, persistent_readback_verified=True)

    try:
        selected_runner = runner_script(plan)
        state['runner_script'] = selected_runner
        save()
        upload(out / 'plan.json', plan['s3_prefix'] + '/plan.json')
        for name in state['queue']:
            if (out / 'cancel.request').exists():
                state['cancelled'] = True
                break
            state['active'] = name
            save()
            with (out / (name + '.log')).open('wb') as log:
                process = subprocess.Popen([str(RUNTIME / 'venv/bin/python'), '-u',
                    str(RUNTIME / 'pipeline' / selected_runner), str(out), name],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=log)
                timeout = plan.get('variant_timeouts', {}).get(name, plan['variant_timeout_seconds'])
                try:
                    code = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    code = 124
            if code:
                raise RuntimeError(name + ' exited ' + str(code))
            result_path = out / ('result_' + name + '.json')
            result = json.loads(result_path.read_text())
            if not result.get('complete'):
                raise RuntimeError('Incomplete candidate ' + name)
            full_path = out / name / 'training_final_state.pt'
            full = torch.load(full_path, map_location='cpu', weights_only=False)
            required = {'model', 'normalizer_aux', 'actor_optimizer', 'critic_optimizer',
                        'actor_steps', 'critic_steps', 'samples', 'torch_rng', 'cuda_rng',
                        'numpy_rng', 'python_rng', 'env_config', 'engine_config', 'agent_config'}
            if not required.issubset(full) or not full.get('isolated_sweep'):
                raise RuntimeError('Full optimizer/normalizer/RNG state incomplete: ' + name)
            metadata = dict(samples=full['samples'], actor_steps=full['actor_steps'],
                            critic_steps=full['critic_steps'], full_state_verified=True)
            del full
            prefix = plan['s3_prefix'] + '/' + name
            result_receipt = upload(result_path, prefix + '/result.json')
            full_receipt = upload(full_path, prefix + '/training_final_state.pt')
            manifest[name] = dict(result=result_receipt, training_final_state=full_receipt,
                                  verified_unix=time.time(), **metadata)
            atomic_json(out / 'artifact_backups.json', manifest)
            upload(out / 'artifact_backups.json', plan['s3_prefix'] + '/artifact_backups.json')
            state['completed'].append(name)
            state['last_backup'] = name
            save()
        state.update(active=None, finished=time.time())
        save()
        upload(out / 'queue_status.json', plan['s3_prefix'] + '/queue_status.json')
        deadline = time.time() + float(plan.get('idle_stop_seconds', 300))
        while time.time() < deadline:
            if (out / 'next-stage-started').exists():
                return
            time.sleep(5)
        stop('Confirmation finished; no successor within idle grace')
    except BaseException as error:
        state.update(active=None, failed=type(error).__name__ + ': ' + str(error), finished=time.time())
        save()
        stop('Confirmation failed: ' + str(error))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('plan')
    prep.add_argument('--directory', default='loco-confirm')
    start = sub.add_parser('launch')
    start.add_argument('--directory', default='loco-confirm')
    start.add_argument('--previous-directory', default='loco-sweeps')
    get = sub.add_parser('fetch')
    get.add_argument('--directory', default='loco-confirm')
    keep = sub.add_parser('preserve')
    keep.add_argument('--directory', default='loco-confirm')
    keep.add_argument('--variants', nargs='*')
    queue = sub.add_parser('queue')
    queue.add_argument('directory')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.plan, args.directory)
    elif args.command == 'launch':
        launch(args.directory, args.previous_directory)
    elif args.command == 'fetch':
        fetch(args.directory)
    elif args.command == 'preserve':
        preserve(args.directory, args.variants)
    elif args.command == 'queue':
        remote_queue(args.directory)


if __name__ == '__main__':
    main()
