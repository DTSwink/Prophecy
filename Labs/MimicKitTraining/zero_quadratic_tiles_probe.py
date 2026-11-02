"""Probe-only zero-product fast path in the pinned native quadratic Hessian.

Every nonzero or nonfinite product uses the original tile arithmetic. A skipped
finite zero product still adds a zero tile in the original accumulation order.
This keeps no previous-state cache and does not change the elliptic cone term.
"""
import inspect
import importlib.util
import sys
from pathlib import Path
from contextlib import contextmanager
import warp as wp
from mujoco_warp._src import solver, types


@wp.kernel(enable_backward=False)
def check_matrix(done: wp.array(dtype=bool), actual: wp.array3d(dtype=float),
                 reference: wp.array3d(dtype=float), counts: wp.array2d(dtype=int),
                 maximum: wp.array(dtype=float)):
    w, i, j = wp.tid()
    if done[w]:
        return
    a, b = actual[w, i, j], reference[w, i, j]
    if i == 0 and j == 0:
        wp.atomic_add(counts, w, 0, actual.shape[1] * actual.shape[2])
    if a != b:
        wp.atomic_add(counts, w, 1, 1)
        wp.atomic_max(maximum, w, wp.abs(a - b))
    if not wp.isfinite(a) or not wp.isfinite(b):
        wp.atomic_add(counts, w, 2, 1)


class ZeroQuadraticTiles:
    def __init__(self, m, d):
        assert m.is_sparse and not solver.SPARSE_CONSTRAINT_JACOBIAN
        self.m, self.d = m, d
        self.kernel = solver.update_gradient_JTDAJ_sparse_tiled(types.TILE_SIZE_JTDAJ_SPARSE, d.njmax)
        source = inspect.getsource(solver.update_gradient_JTDAJ_sparse_tiled)
        source = source.replace('@cache_kernel\n', '', 1)
        source = source.replace('def update_gradient_JTDAJ_sparse_tiled(tile_size: int, njmax: int):',
            'def zero_JTDAJ_sparse_tiled(tile_size: int, njmax: int, audit: bool):\n  AUDIT = audit', 1)
        marker = '    ctx_h_out: wp.array3d(dtype=float),'
        assert source.count(marker) == 1
        source = source.replace(marker, '    tile_counts: wp.array2d(dtype=int),\n' + marker, 1)
        old = '''      J_ki = wp.tile_map(wp.mul, wp.tile_transpose(J_ki), wp.tile_broadcast(D_k, shape=(TILE_SIZE, TILE_SIZE)))

      sum_val += wp.tile_matmul(J_ki, J_kj)'''
        new = '''      if wp.static(AUDIT):
        wp.tile_atomic_add(tile_counts[worldid], wp.tile_ones(shape=1, dtype=int), offset=0)
      zero_product = False
      if wp.tile_extract(wp.tile_sum(wp.tile_map(nonzero, D_k)), 0) == 0:
        bad_i = wp.tile_extract(wp.tile_sum(wp.tile_map(nonfinite, J_ki)), 0)
        bad_j = wp.tile_extract(wp.tile_sum(wp.tile_map(nonfinite, J_kj)), 0)
        zero_product = bad_i == 0 and bad_j == 0
      if zero_product:
        if wp.static(AUDIT):
          wp.tile_atomic_add(tile_counts[worldid], wp.tile_ones(shape=1, dtype=int), offset=1)
        sum_val += wp.tile_zeros(shape=(TILE_SIZE, TILE_SIZE), dtype=wp.float32)
      else:
        weighted_J = wp.tile_map(wp.mul, wp.tile_transpose(J_ki), wp.tile_broadcast(D_k, shape=(TILE_SIZE, TILE_SIZE)))
        sum_val += wp.tile_matmul(weighted_J, J_kj)'''
        assert source.count(old) == 1
        source = source.replace(old, new, 1)
        header = Path(solver.__file__).read_text().split('import dataclasses', 1)[0]
        helpers = '''import warp as wp
from mujoco_warp._src.solver import sqrt, state_check, active_check
@wp.func
def nonzero(value: float):
  return int(value != 0.0)
@wp.func
def nonfinite(value: float):
  return int(not wp.isfinite(value))
'''
        generated = Path(__file__).with_name('zero_quadratic_generated.py')
        generated.write_text(header + helpers + source)
        name = 'zero_quadratic_generated'
        spec = importlib.util.spec_from_file_location(name, generated)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        self.kernels = {audit: module.zero_JTDAJ_sparse_tiled(types.TILE_SIZE_JTDAJ_SPARSE, d.njmax, audit)
                        for audit in [False, True]}
        self.original = wp.launch_tiled
        self.audit = False
        self.hits = 0
        self.reference = wp.zeros((d.nworld, m.nv_pad, m.nv_pad), dtype=float)
        self.counts = wp.zeros((d.nworld, 3), dtype=int)
        self.maximum = wp.zeros(d.nworld, dtype=float)
        self.tile_counts = wp.zeros((d.nworld, 2), dtype=int)

    def tiled(self, kernel, *args, **kwargs):
        if kernel is not self.kernel:
            return self.original(kernel, *args, **kwargs)
        assert not args and len(kwargs['inputs']) == 5
        inputs = list(kwargs['inputs'])
        self.original(self.kernels[self.audit], **dict(kwargs, inputs=[*inputs, self.tile_counts]))
        if self.audit:
            self.original(kernel, **dict(kwargs, outputs=[self.reference]))
            h = kwargs['outputs'][0]
            wp.launch(check_matrix, dim=h.shape,
                      inputs=[inputs[-1], h, self.reference, self.counts, self.maximum])
        self.hits += 1

    @contextmanager
    def capture(self):
        previous = wp.launch_tiled
        self.original = previous
        self.hits = 0
        try:
            wp.launch_tiled = self.tiled
            yield self
        finally:
            wp.launch_tiled = previous
