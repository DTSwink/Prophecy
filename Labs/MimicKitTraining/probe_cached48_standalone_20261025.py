"""Small rejection gate before constructing any expensive training environment."""
import hashlib
import inspect
import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
sys.path.insert(0, str(HERE))
import torch
import warp as wp
from mujoco_warp._src import solver
from cholesky_cached48_probe import cached48


def main():
    import cholesky_cached48_probe
    source = Path(inspect.getfile(cholesky_cached48_probe)).resolve()
    assert source.parent == HERE, source
    torch.set_num_threads(1)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.manual_seed(6846)
    wp.init()
    wp.set_device('cuda:0')
    worlds = 2048 if '--timing' in sys.argv else 256
    done = torch.zeros(worlds, dtype=torch.bool, device='cuda')
    done[::7] = True
    grad = torch.randn(worlds, 48, 1, device='cuda')
    grad[:, 40:] = 0
    h = torch.zeros(worlds, 48, 48, device='cuda')
    h[:, 40:, 40:] = torch.eye(8, device='cuda')
    native_factor = torch.zeros_like(h)
    edge_factor = torch.zeros_like(h)
    native = torch.full_like(grad, 17.)
    candidate = native.clone()
    native_kernel = solver.update_gradient_cholesky_blocked(16, 48)
    shared = [wp.from_torch(done), wp.from_torch(grad), wp.from_torch(h)]
    results = []
    start = time.time()
    for diagonal in [5., 1., .1]:
        a = torch.randn(worlds, 40, 40, device='cuda') * .15
        h[:, :40, :40] = a @ a.transpose(-1, -2) + diagonal * torch.eye(40, device='cuda')
        wp.launch_tiled(native_kernel, dim=worlds,
                        inputs=shared + [wp.from_torch(native_factor)],
                        outputs=[wp.from_torch(native)], block_dim=32)
        wp.launch_tiled(cached48, dim=worlds,
                        inputs=shared + [wp.from_torch(edge_factor)],
                        outputs=[wp.from_torch(candidate)], block_dim=32)
        wp.synchronize()
        delta = candidate - native
        scale = native.double().norm(dim=(1, 2)).clamp_min(1.)
        relative = delta.double().norm(dim=(1, 2)) / scale
        row = dict(diagonal=diagonal, elements=native.numel(),
                   different_elements=int((candidate != native).sum()),
                   finite=bool(torch.isfinite(candidate).all()),
                   max_abs=float(delta.abs().max()),
                   max_relative=float(relative.max()),
                   rms_relative=float(relative.square().mean().sqrt()),
                   skipped_worlds_unchanged=bool(torch.equal(candidate[done], native[done])))
        results.append(row)
        print(json.dumps(row), flush=True)
    result = dict(source=str(source), sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  elapsed=time.time()-start, cases=results,
                  exact=all(r['different_elements'] == 0 and r['finite'] for r in results),
                  production_changed=False,
                  note='Synthetic SPD gate only; does not prove live solver fidelity or speed.')
    if '--timing' in sys.argv:
        timings = []
        for active_fraction in [1., .25, .05]:
            done.copy_(torch.arange(worlds, device='cuda') >= int(worlds*active_fraction))
            graphs = {}
            for name, kernel, factor, output in [('native', native_kernel, native_factor, native),
                                                  ('cached48', cached48, edge_factor, candidate)]:
                with wp.ScopedCapture() as cap:
                    for _ in range(32):
                        wp.launch_tiled(kernel, dim=worlds,
                                        inputs=shared+[wp.from_torch(factor)],
                                        outputs=[wp.from_torch(output)], block_dim=32)
                graphs[name] = cap.graph
                wp.capture_launch(cap.graph)
            wp.synchronize()
            for name in ['native', 'cached48', 'cached48', 'native']*3:
                start_event, end_event = wp.Event(enable_timing=True), wp.Event(enable_timing=True)
                wp.record_event(start_event)
                wp.capture_launch(graphs[name])
                wp.record_event(end_event)
                wp.synchronize()
                timings.append(dict(active_fraction=active_fraction, variant=name,
                                    microseconds=wp.get_event_elapsed_time(start_event, end_event)*1000/32))
        result['timing'] = timings
        result['note'] += ' Timing shares GPU with production; no end-to-end claim.'
    (OUT/'complete.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        (OUT/'failure.txt').write_text(traceback.format_exc())
        raise
