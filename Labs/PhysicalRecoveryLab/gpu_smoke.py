"""Small CUDA-graph smoke test before allocating the humanoid training batch."""
from pathlib import Path
import json
import time
import numpy as np
import mujoco
import mujoco_warp as mjw
import warp as wp

XML = """<mujoco><option timestep="0.004166666666666667" gravity="0 0 -9.81"/>
<worldbody><geom type="plane" size="10 10 .1" friction=".7 0 0"/>
<body pos="0 0 1"><freejoint/><geom type="sphere" size=".1" mass="1" friction=".7 0 0"/></body>
</worldbody></mujoco>"""

def main():
    wp.init()
    model = mujoco.MjModel.from_xml_string(XML)
    data = mujoco.MjData(model)
    with wp.ScopedDevice("cuda:0"):
        wm = mjw.put_model(model)
        wd = mjw.put_data(model, data, nworld=128, nconmax=8, njmax=32)
        start = time.perf_counter()
        mjw.step(wm, wd)
        wp.synchronize()
        warmup = time.perf_counter()-start
        with wp.ScopedCapture() as capture:
            mjw.step(wm, wd)
        start = time.perf_counter()
        for _ in range(480):
            wp.capture_launch(capture.graph)
        wp.synchronize()
        elapsed = time.perf_counter()-start
        qpos = wd.qpos.numpy()
    z = qpos[:, 2]
    assert np.isfinite(qpos).all() and np.max(np.abs(z-.1)) < .015, z
    report = {"mujoco":mujoco.__version__, "warp":wp.__version__, "worlds":128,
              "cuda_graph":True, "warmup_seconds":warmup, "simulation_seconds":2,
              "wall_seconds":elapsed, "world_steps_per_second":128*480/elapsed,
              "final_z_range_m":[float(z.min()),float(z.max())], "passed":True}
    out=Path(__file__).resolve().parents[2]/"Saved/Robotics/gpu-smoke.json"
    out.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2),flush=True)

if __name__ == "__main__":
    main()
