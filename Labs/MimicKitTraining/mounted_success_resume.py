"""Restore through Runpod's documented network-volume mount, without S3 HTTP."""
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Saved/MimicKitEquipment"
os.environ["MIMICKIT_STATE_DIR"] = str(OUT)
import cloud


def allocate():
    old = cloud.state()
    assert cloud.rp.request_json("GET", "/pods/" + old["pod_id"])["desiredStatus"] == "EXITED"
    name = "mimickit-mounted-success-" + str(int(time.time()))
    public = cloud.rp.PRIVATE_KEY.with_suffix(".pub").read_text().strip()
    payload = dict(
        name=name, cloudType="SECURE", computeType="GPU",
        gpuTypeIds=["NVIDIA L4"], gpuTypePriority="custom", gpuCount=1,
        dataCenterIds=["EU-RO-1"], dataCenterPriority="custom",
        networkVolumeId=cloud.rp.VOLUME_ID, volumeMountPath="/persistent",
        imageName="runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04",
        containerDiskInGb=40, minVCPUPerGPU=4, minRAMPerGPU=16,
        ports=["22/tcp"], supportPublicIp=True, interruptible=False,
        env={"PUBLIC_KEY": public, "SSH_PUBLIC_KEY": public},
        dockerEntrypoint=[], dockerStartCmd=[],
    )
    pod = cloud.rp.request_json("POST", "/pods", payload)
    # Record returned identity before any SSH/setup operation.
    (OUT / "mounted-success-allocation.json").write_text(json.dumps(pod))
    if not 0 < float(pod.get("costPerHr", 999)) <= .59:
        cloud.rp.request_json("POST", "/pods/" + pod["id"] + "/stop")
        raise RuntimeError("Price exceeds approved ceiling; stopped")
    retained = OUT / "retained-pods" / old["pod_id"]
    retained.mkdir(parents=True, exist_ok=True)
    for filename in ("pod.json", "runtime_control.json", "active_run.json"):
        source = OUT / filename
        if source.exists():
            source.replace(retained / (str(int(time.time())) + "-" + filename))
    cloud.save(dict(pod_id=pod["id"], name=name, gpu="NVIDIA L4",
                    cost_per_hour=pod["costPerHr"], created_unix=time.time(),
                    max_initial_runtime_seconds=600, cloud_type="SECURE",
                    network_volume_id=cloud.rp.VOLUME_ID))
    (OUT / "runtime_control.json").write_text(json.dumps(dict(
        pod_id=pod["id"], hard_stop_unix=time.time()+600, until_stopped=False)))
    with (OUT / "mounted-success-guard.log").open("ab") as log:
        guard = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("local_guard.py"))],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=0x08000000)
    print(json.dumps(dict(pod=pod["id"], guard=guard.pid)), flush=True)
    cloud.connect()


def restore():
    plan = json.loads((OUT / "getup-success-prepared.json").read_text())
    code = """
import hashlib,json,os,shutil,subprocess,sys,time,zipfile
from pathlib import Path
p=Path('/persistent')
assert p.is_mount(), 'Expected persistent network-volume mount'
r=Path('/workspace/mimickit_trial')
durable=p/'mimickit/trials'/POD
durable.mkdir(parents=True,exist_ok=True)
r.parent.mkdir(exist_ok=True)
if not r.exists():r.symlink_to(durable,target_is_directory=True)
assert r.resolve()==durable.resolve()
def checked(key,sha,dest):
 src=p/key
 h=hashlib.file_digest(src.open('rb'),'sha256').hexdigest()
 assert h==sha, 'Persistent source checksum mismatch'
 shutil.copyfile(src,dest)
 assert hashlib.file_digest(dest.open('rb'),'sha256').hexdigest()==sha
checked(PLAN['source']['key'],PLAN['source']['sha256'],r/'source.zip')
checked(PLAN['checkpoint']['preserved_key'],PLAN['checkpoint']['sha256'],r/'resume.zip')
with zipfile.ZipFile(r/'source.zip') as z:z.extractall(r)
sys.path.insert(0,str(r/'pipeline'))
import runtime_cache
manifest=json.loads((p/'mimickit/runtime/latest_verified.json').read_text())
manifest['kernels']=json.loads((p/'mimickit/runtime/kernels_verified.json').read_text())
(r/'runtime-cache.json').write_text(json.dumps(manifest))
def mounted_download(item,path):checked(item['key'],item['sha256'],path)
runtime_cache.download=mounted_download
runtime_cache.restore()
(r/'success-download-ready').touch()
print('Persistent source, checkpoint and runtime verified',flush=True)
""".replace("POD", repr(cloud.state()["pod_id"])).replace("PLAN", repr(plan))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "restore.py"
        path.write_text(code)
        cloud.rp.scp(cloud.state()["connection"], path, "/tmp/mimickit-mounted-restore.py", timeout=30)
    print(cloud.ssh("nohup timeout 360 python /tmp/mimickit-mounted-restore.py > /tmp/mimickit-mounted-restore.log 2>&1 < /dev/null & echo $!", timeout=20))


if __name__ == "__main__":
    globals()[sys.argv[1]]()
