"""User-approved, ten-minute native MJWarp audit on one replacement L4."""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Saved/MimicKitTransfer/vanilla-calibration'
STATE = OUT / 'gpu-cloud'
os.environ['MIMICKIT_STATE_DIR'] = str(STATE)
sys.path.insert(0, str(ROOT / 'Labs/MimicKitTraining'))
import cloud
from billing_stop import stop_and_confirm


def main():
    guard = None
    receipt = {}
    remote = '/workspace/mimickit_trial'
    original_deadline = 1792304718.265493
    try:
        assert time.time() + 600 < original_deadline
        cloud.allocate('NVIDIA L4', .59, 'SECURE', seconds=600,
                       name='mimickit-native-audit-20261018')
        state = cloud.state()
        deadline = min(original_deadline, state['created_unix'] + 600)
        control = dict(pod_id=state['pod_id'], hard_stop_unix=deadline)
        (STATE / 'runtime_control.json').write_text(json.dumps(control))
        guard_log = (STATE / 'local-guard.log').open('w')
        guard = subprocess.Popen([sys.executable, str(ROOT / 'Labs/MimicKitTraining/local_guard.py')],
                                 stdout=guard_log, stderr=guard_log, creationflags=0x08000000)
        receipt.update(pod=state['pod_id'], started_unix=state['created_unix'],
                       hard_stop_unix=deadline, max_gpu_cost=.10, guard_pid=guard.pid)
        (OUT / 'replacement-session.json').write_text(json.dumps(receipt, indent=2))
        cloud.connect()
        print('Connected; ten-minute billing guard active.', flush=True)
        cloud.ssh('mkdir -p ' + remote + '/native-audit')
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp) / 'private.json'
            private.write_text(json.dumps(dict(pod_id=state['pod_id'], deadline_unix=deadline,
                                               runpod_api_key=cloud.rp.load_api_key())))
            cloud.rp.scp(cloud.state()['connection'], private, remote + '/private.json', timeout=30)
        for filename in ('guard.py', 'billing_stop.py', 'runtime_deadline.py', 'runtime_cache.py'):
            cloud.rp.scp(cloud.state()['connection'], ROOT / 'Labs/MimicKitTraining' / filename,
                         remote + '/' + filename, timeout=30)
        cloud.rp.scp(cloud.state()['connection'], STATE / 'runtime_control.json', remote + '/runtime_control.json', timeout=30)
        cloud.ssh('chmod 600 ' + remote + '/private.json; cd ' + remote + '; nohup python guard.py > guard.log 2>&1 < /dev/null &')
        cloud.prepare_runtime_cache()
        print('Restoring cached runtime directly from persistent storage.', flush=True)
        restore = cloud.ssh('cd ' + remote + '; timeout 180 python runtime_cache.py restore', timeout=190)
        (OUT / 'replacement-restore.log').write_text(restore)
        cloud.rp.scp(cloud.state()['connection'], OUT / 'gpu-packet.tar.gz', remote + '/native-audit/packet.tar.gz', timeout=40)
        cloud.ssh('tar -xzf ' + remote + '/native-audit/packet.tar.gz -C ' + remote + '/native-audit')
        available = int(deadline - time.time() - 45)
        assert available > 60, 'Not enough time after runtime restore; stopping safely'
        print('Native audit started with ' + str(available) + ' seconds available.', flush=True)
        try:
            cloud.ssh('cd ' + remote + '/native-audit; timeout ' + str(available) +
                      ' ../venv/bin/python -u validate_vanilla_gpu.py . > gpu-audit.log 2>&1', timeout=available+10)
        finally:
            log = cloud.ssh('tail -c 40000 ' + remote + '/native-audit/gpu-audit.log', timeout=15)
            (OUT / 'gpu-audit.log').write_text(log)
            result = cloud.ssh('if [ -f ' + remote + '/native-audit/gpu-results.json ]; then cat ' +
                               remote + '/native-audit/gpu-results.json; fi', timeout=15)
            if result.strip():
                (OUT / 'gpu-results.json').write_text(result)
                receipt['result'] = json.loads(result)
                print(result, flush=True)
        # Unique numerical motion evidence, compressed before download.
        cloud.ssh('cd ' + remote + '/native-audit; tar -czf gpu-evidence.tar.gz *_gpu.npz gpu-results.json gpu-audit.log', timeout=20)
        connection = cloud.state()['connection']
        # Use the SSH transport to fetch binary output without shell quoting local paths.
        fetched = subprocess.run(cloud.rp.ssh_base(connection) + ['cat', remote + '/native-audit/gpu-evidence.tar.gz'],
                                 capture_output=True, timeout=30, check=True)
        (OUT / 'gpu-evidence.tar.gz').write_bytes(fetched.stdout)
        receipt['evidence_bytes'] = len(fetched.stdout)
    except Exception as error:
        receipt['failure'] = str(error)
        print('Audit failure: ' + str(error), flush=True)
    finally:
        if (STATE / 'pod.json').exists():
            state = cloud.state()
            receipt['stop'] = stop_and_confirm(state['pod_id'], cloud.rp.load_api_key(),
                                               STATE / 'stopped.json', 'native audit completed or failed')
            print('Replacement L4 confirmed stopped.', flush=True)
        receipt['ended_unix'] = time.time()
        (OUT / 'replacement-session.json').write_text(json.dumps(receipt, indent=2))
        if guard is not None and guard.poll() is None:
            guard.terminate()
            guard.wait(timeout=10)


if __name__ == '__main__':
    main()
