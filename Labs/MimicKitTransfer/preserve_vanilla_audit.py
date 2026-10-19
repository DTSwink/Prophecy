"""Preserve small audit evidence before deleting only its disposable pod."""
import hashlib, json, os, sys, tarfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Saved/MimicKitTransfer/vanilla-calibration'
os.environ['MIMICKIT_STATE_DIR'] = str(OUT / 'gpu-cloud')
sys.path.insert(0, str(ROOT / 'Labs/MimicKitTraining'))
import cloud


def main():
    state = cloud.state()
    assert state['pod_id'] == 'u7yyhwcg8xt179'
    stopped = json.loads((OUT / 'gpu-cloud/stopped.json').read_text())
    assert stopped['confirmed'] and stopped['state'] == 'EXITED'
    archive = OUT / 'native-audit-20261018.tar.gz'
    files = list(OUT.glob('*.json')) + [OUT / 'gpu-evidence.tar.gz', OUT / 'gpu-packet.tar.gz']
    scripts = ('calibrate_vanilla.py', 'package_vanilla_validation.py', 'validate_vanilla_gpu.py',
               'summarize_vanilla_audit.py', 'run_replacement_vanilla_audit.py', 'preserve_vanilla_audit.py')
    files += [ROOT / 'Labs/MimicKitTransfer' / name for name in scripts]
    files += [ROOT / 'Docs/MimicKitTraining.md', ROOT / 'Docs/MimicKitTransfer.md']
    # Explicit allowlist excludes cloud/private credentials and unrelated data.
    with tarfile.open(archive, 'w:gz', compresslevel=1) as packed:
        for path in sorted(set(files)):
            packed.add(path, arcname=path.relative_to(ROOT).as_posix())
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    key = 'mimickit/diagnostics/native-audit-20261018-' + sha[:12] + '.tar.gz'
    client = cloud.s3()
    client.upload_file(str(archive), cloud.rp.VOLUME_ID, key, ExtraArgs={'Metadata': {'sha256': sha}})
    body = client.get_object(Bucket=cloud.rp.VOLUME_ID, Key=key)['Body']
    digest = hashlib.sha256()
    for chunk in iter(lambda: body.read(4*1024*1024), b''):
        digest.update(chunk)
    body.close()
    assert digest.hexdigest() == sha
    receipt = dict(key=key, bytes=archive.stat().st_size, sha256=sha, readback_verified=True)
    (OUT / 'persistent-audit.json').write_text(json.dumps(receipt, indent=2))
    pod = cloud.rp.request_json('GET', '/pods/' + state['pod_id'])
    assert pod['desiredStatus'] == 'EXITED' and pod['name'] == 'mimickit-native-audit-20261018'
    cloud.rp.request_json('DELETE', '/pods/' + state['pod_id'])
    remaining = cloud.rp.request_json('GET', '/pods')
    assert not any(p['id'] == state['pod_id'] for p in remaining)
    receipt.update(disposable_pod_deleted=state['pod_id'], verified_unix=time.time())
    (OUT / 'persistent-audit.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
