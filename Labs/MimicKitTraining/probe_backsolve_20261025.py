"""Standalone sparse substitution parity/timing, including aliases and nonfinites."""
import json
import time
import traceback
from pathlib import Path
import torch
import warp as wp
import mujoco
import mujoco_warp as mjw
from fused_backsolve_probe import FusedBacksolve

ROOT = Path('/workspace/mimickit_trial')
OUT = ROOT / 'perf-lossless-20261024'


def main():
    torch.set_num_threads(1)
    wp.init()
    wp.set_device('cuda:0')
    mm = mujoco.MjModel.from_binary_path(str(OUT / 'native-model.mjb'))
    cpu = mujoco.MjData(mm)
    mujoco.mj_forward(mm, cpu)
    m = mjw.put_model(mm)
    d = mjw.put_data(mm, cpu, nworld=2048, nconmax=150, njmax=450)
    fused = FusedBacksolve(m, d)
    checks = []
    for trial in range(8):
        pos = wp.to_torch(d.qpos)
        for joint, kind in enumerate(mm.jnt_type):
            start = int(mm.jnt_qposadr[joint])
            if kind in (mujoco.mjtJoint.mjJNT_FREE, mujoco.mjtJoint.mjJNT_BALL):
                start += 3 if kind == mujoco.mjtJoint.mjJNT_FREE else 0
                q = torch.randn((d.nworld, 4), device='cuda')
                pos[:, start:start + 4] = q / q.norm(dim=1, keepdim=True)
        mjw.kinematics(m, d)
        mjw.com_pos(m, d)
        mjw.crb(m, d)
        mjw.factor_m(m, d)
        width = m.nv if trial % 2 == 0 else m.nv_pad
        y = wp.zeros((d.nworld, width), dtype=float)
        x = wp.zeros_like(y)
        wp.to_torch(y).normal_()
        saved = wp.clone(y)
        outputs = []
        alias = trial >= 4
        for method in [fused.original, fused.original, fused.apply]:
            wp.copy(y, saved)
            target = y if alias else x
            method(m, d, d.qLD, d.qLDiagInv, target, y)
            wp.synchronize()
            outputs.append(wp.to_torch(target).clone())
        baseline, repeat, candidate = outputs
        row = dict(trial=trial, width=width, alias=alias,
                   max_error=float((baseline - candidate).abs().max()),
                   reference_repeat=float((baseline - repeat).abs().max()),
                   relative_l2=float(torch.linalg.vector_norm(baseline - candidate) / torch.linalg.vector_norm(baseline)),
                   padding_exact=bool(torch.equal(baseline[:, m.nv:], candidate[:, m.nv:])))
        assert torch.isfinite(candidate).all() and row['relative_l2'] < 2e-6 and row['padding_exact'], row
        checks.append(row)
    y = wp.zeros((d.nworld, m.nv), dtype=float)
    x = wp.zeros_like(y)
    nonfinite = []
    for index, value in [(0, float('nan')), (6, float('inf')), (15, -float('inf'))]:
        wp.to_torch(y).normal_()
        wp.to_torch(y)[:, index] = value
        outputs = []
        for method in [fused.original, fused.apply]:
            method(m, d, d.qLD, d.qLDiagInv, x, y)
            outputs.append(wp.to_torch(x).clone())
        a, b = outputs
        assert torch.equal(torch.isnan(a), torch.isnan(b))
        assert torch.equal(torch.isposinf(a), torch.isposinf(b))
        assert torch.equal(torch.isneginf(a), torch.isneginf(b))
        nonfinite.append(dict(index=index, classification_exact=True))
    wp.to_torch(y).normal_()
    graphs = []
    for method in [fused.original, fused.apply]:
        with wp.ScopedCapture() as capture:
            for _ in range(16):
                method(m, d, d.qLD, d.qLDiagInv, x, y)
        graphs.append(capture.graph)
    timings = []
    for index in [0, 1, 1, 0] * 3:
        wp.capture_launch(graphs[index])
        wp.synchronize()
        started = time.perf_counter()
        for _ in range(10):
            wp.capture_launch(graphs[index])
        wp.synchronize()
        timings.append(dict(optimized=bool(index), seconds_per_solve=(time.perf_counter() - started) / 160))
    report = dict(checks=checks, nonfinite=nonfinite, timings=timings, levels=fused.levels)
    (OUT / 'backsolve-screen-complete.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        (OUT / 'backsolve-screen-failure.txt').write_text(traceback.format_exc())
        raise
