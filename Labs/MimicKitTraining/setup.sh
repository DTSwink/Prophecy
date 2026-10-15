set -eu
cd /workspace/mimickit_trial
export PIP_DISABLE_PIP_VERSION_CHECK=1
if python pipeline/runtime_cache.py restore; then
    exit 0
else
    status=$?
    test "$status" -eq 3 || exit "$status"
fi
# Small-file installation is much faster on the container disk than /workspace.
mkdir -p /opt/mimickit-runtime
python -m venv --system-site-packages /opt/mimickit-runtime/venv
ln -s /opt/mimickit-runtime/venv venv
venv/bin/python -m pip install 'newton[sim]==1.0.0' 'warp-lang==1.12.1' gymnasium 'diffusers>=0.36.0' moviepy matplotlib numpy pyyaml pyglet tensorboardX tensorboard 'wandb>=0.17.4' scipy boto3
venv/bin/python -m pip freeze > runtime-freeze.txt
venv/bin/python - <<'PY'
import json,torch,newton,mujoco,mujoco_warp,warp,importlib.metadata as m
print(json.dumps({'gpu':torch.cuda.get_device_name(0),'torch':torch.__version__,
 'cuda':torch.version.cuda,'versions':{n:m.version(n) for n in ['newton','warp-lang','mujoco','mujoco-warp']}}))
PY
