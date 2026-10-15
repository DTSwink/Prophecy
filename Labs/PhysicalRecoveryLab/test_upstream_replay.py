"""CPU-only observer tests; never publishes synthetic poses to the user's runs."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import mujoco
import numpy as np
import torch
import warp as wp

import replay_upstream as replay

wp.init()
root = Path(__file__).resolve().parents[2]
xml = root/'Saved/Robotics/vendor/mjlab_playground/src/mjlab_playground/asset_zoo/robots/booster_t1/xmls/t1.xml'
model = mujoco.MjModel.from_xml_path(str(xml))
data = mujoco.MjData(model)
mujoco.mj_kinematics(model, data)
positions = torch.tensor(data.xpos[None], dtype=torch.float32)
quats = torch.tensor(data.xquat[None], dtype=torch.float32)
raw = SimpleNamespace(sim=SimpleNamespace(mj_model=model, wp_data=SimpleNamespace(
    xpos=wp.from_torch(positions, dtype=wp.vec3), xquat=wp.from_torch(quats, dtype=wp.quat))),
    device='cpu', step_dt=.02, physics_dt=.005, episode_length_buf=torch.tensor([0]),
    common_step_counter=0, num_envs=4096)
with TemporaryDirectory() as temp:
    replay.STEPPER = Path(temp)
    writer = replay.UpstreamReplay(raw, 'test', capacity=5)
    for step in range(9):
        positions[0, :, 0] = step
        raw.episode_length_buf[0] = step if step < 6 else step-6
        writer.capture()
    writer.publish(157, 'checkpoint156')
    payload = json.loads((writer.debug/'last_batch_rollout.json').read_text())
    actual = np.array(payload['positions'][0])
    assert len(actual) == 3  # Most recent episode only, ring-buffer order preserved.
    np.testing.assert_allclose(actual[:, 0, 0], [6, 7, 8])
    np.testing.assert_allclose(actual[-1], positions[0, 1:].numpy() @ replay.WORLD_TO_VIEW.T)
    assert payload['fps'] == 50
    assert any(s['kind'] == 'mesh' for s in writer.shapes)
    assert sum('foot' in s['bone'] for s in writer.shapes) == 8
    assert np.isfinite(np.array(payload['basis'])).all()
    raw.episode_length_buf[0] = 0
    writer.capture()
    writer.publish(158, 'checkpoint156')
    payload = json.loads((writer.debug/'last_batch_rollout.json').read_text())
    assert len(payload['positions'][0]) == 3  # A one-frame reset doesn't erase a usable clip.
    writer.close()
    assert not writer.marker.exists()
print('PASS: actual transforms, axes, ring wrap, reset boundary, feet and trunk hull')
