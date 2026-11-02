"""Disposable FP32 Newton matrix-solve comparison on the exact model dimensions."""
import json
import time
import traceback
from pathlib import Path
import numpy as np
import torch
import warp as wp
import mujoco
import mujoco_warp as mjw
from mujoco_warp._src import solver

ROOT = Path('/workspace/mimickit_trial')
OUT = ROOT / 'perf-lossless-20261024'


def main():
    torch.set_num_threads(1)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    wp.init()
    wp.set_device('cuda:0')
    mm = mujoco.MjModel.from_binary_path(str(OUT / 'native-model.mjb'))
    m = mjw.put_model(mm)
    d = mjw.make_data(mm, nworld=2048, nconmax=150, njmax=450)
    ctx = solver.create_solver_context(m, d)
    ctx.done.zero_()
    n = m.nv
    assert n == 40
    h = wp.to_torch(ctx.h)
    g = wp.to_torch(ctx.grad)
    result = wp.to_torch(ctx.Mgrad)
    variants = [('blocked32', 32, False), ('blocked64', 64, False), ('direct64', 64, True)]
    print(json.dumps(dict(nv=n, nv_pad=m.nv_pad, variants=variants)), flush=True)

    def run(variant):
        _, block, direct = variant
        if direct:
            wp.launch_tiled(solver.update_gradient_cholesky(n), dim=d.nworld,
                            inputs=[ctx.grad, ctx.h, ctx.done], outputs=[ctx.Mgrad], block_dim=block)
        else:
            m.block_dim.update_gradient_cholesky_blocked = block
            solver._cholesky_factorize_solve(m, d, ctx)

    checks = []
    graphs = []
    for trial, condition in enumerate([1., 100., 10000., 1000000.]):
        generator = torch.Generator(device='cuda').manual_seed(9270 + trial)
        matrix = torch.randn((d.nworld, n, n), generator=generator, device='cuda') / n**.5
        scales = torch.logspace(0, np.log10(condition), n, device='cuda').sqrt()
        matrix *= scales[None, :, None]
        h.zero_()
        h[:, :n, :n] = matrix @ matrix.transpose(-1, -2)
        h[:, torch.arange(n), torch.arange(n)] += 1.
        g.zero_()
        g[:, :n] = torch.randn((d.nworld, n), generator=generator, device='cuda')
        outputs = {}
        for variant in variants:
            run(variant)
            wp.synchronize()
            outputs[variant[0]] = result[:, :n].clone()
        reference = torch.linalg.solve(h[:32, :n, :n].double(), g[:32, :n].double())
        rows = {}
        for name, value in outputs.items():
            difference = value - outputs['blocked32']
            rows[name] = dict(finite=bool(torch.isfinite(value).all()),
                              equal_to_baseline=bool(torch.equal(value, outputs['blocked32'])),
                              max_difference=float(difference.abs().max()),
                              relative_l2=float(torch.linalg.vector_norm(difference) /
                                                torch.linalg.vector_norm(outputs['blocked32'])),
                              relative_l2_to_fp64=float(torch.linalg.vector_norm(value[:32].double() - reference) /
                                                       torch.linalg.vector_norm(reference)))
            assert rows[name]['finite'], (condition, name)
        checks.append(dict(condition_scale=condition, variants=rows))
        (OUT / 'cholesky-screen-checks.json').write_text(json.dumps(checks, indent=2))
        print(json.dumps(checks[-1]), flush=True)
    for variant in variants:
        with wp.ScopedCapture() as capture:
            for _ in range(16):
                run(variant)
        graphs.append(capture.graph)
    timings = []
    for order in [list(range(len(variants))), list(reversed(range(len(variants))))] * 2:
        for index in order:
            wp.capture_launch(graphs[index])
            wp.synchronize()
            started = time.perf_counter()
            for _ in range(10):
                wp.capture_launch(graphs[index])
            wp.synchronize()
            timings.append(dict(variant=variants[index][0], seconds_per_solve=(time.perf_counter() - started) / 160))
    report = dict(nv=n, nv_pad=m.nv_pad, worlds=d.nworld, checks=checks, timings=timings,
                  note='Synthetic SPD matrices screen kernel candidates only; production physics/learning parity is not established.')
    (OUT / 'cholesky-screen-complete.json').write_text(json.dumps(report, indent=2))
    print('Completed Cholesky screen', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        (OUT / 'cholesky-screen-failure.txt').write_text(traceback.format_exc())
        raise
