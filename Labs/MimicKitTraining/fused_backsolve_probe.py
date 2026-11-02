"""Fuse the backend's existing sparse LDL substitution schedule into one block."""
from contextlib import contextmanager
import numpy as np
import warp as wp
from mujoco_warp._src import smooth


@wp.func_native('__syncthreads();')
def block_barrier():
    pass


@wp.kernel(enable_backward=False)
def fused_backsolve(nv: int, width: int, levels: int,
                    offsets: wp.array(dtype=int), updates: wp.array(dtype=wp.vec3i),
                    L: wp.array3d(dtype=float), D: wp.array2d(dtype=float),
                    y: wp.array2d(dtype=float), x: wp.array2d(dtype=float)):
    world, lane = wp.tid()
    for index in range(lane, width, 32):
        x[world, index] = y[world, index]
    block_barrier()
    for reverse_level in range(levels):
        level = levels - reverse_level - 1
        for node in range(offsets[level] + lane, offsets[level + 1], 32):
            update = updates[node]
            i, k, address = update[0], update[1], update[2]
            wp.atomic_sub(x[world], i, L[world, 0, address] * x[world, k])
        block_barrier()
    for index in range(lane, nv, 32):
        x[world, index] *= D[world, index]
    block_barrier()
    for level in range(levels):
        for node in range(offsets[level] + lane, offsets[level + 1], 32):
            update = updates[node]
            i, k, address = update[0], update[1], update[2]
            wp.atomic_sub(x[world], k, L[world, 0, address] * x[world, i])
        block_barrier()


class FusedBacksolve:
    def __init__(self, m, d):
        assert m.is_sparse
        groups = [a.numpy() for a in m.qLD_updates]
        self.offsets = wp.array(np.cumsum([0] + [len(a) for a in groups]).astype(np.int32), device=d.qpos.device)
        self.updates = wp.array(np.concatenate(groups).astype(np.int32), dtype=wp.vec3i, device=d.qpos.device)
        self.m, self.d, self.levels = m, d, len(groups)
        self.original = smooth._solve_LD_sparse
        self.hits = 0

    def apply(self, m, d, L, D, x, y):
        assert x.shape == y.shape and x.shape[1] >= m.nv
        wp.launch(fused_backsolve, dim=(d.nworld, 32), block_dim=32,
                  inputs=[m.nv, y.shape[1], self.levels, self.offsets, self.updates, L, D, y], outputs=[x])

    @contextmanager
    def capture(self):
        def wrapped(m, d, L, D, x, y):
            if m is self.m and d is self.d:
                self.hits += 1
                return self.apply(m, d, L, D, x, y)
            return self.original(m, d, L, D, x, y)
        try:
            smooth._solve_LD_sparse = wrapped
            yield self
        finally:
            smooth._solve_LD_sparse = self.original
