"""Experimental direct 40-DoF Cholesky solve; no convergence/precision changes."""
from contextlib import contextmanager
import warp as wp
from mujoco_warp._src import solver


class DirectCholesky:
    def __init__(self, m, d):
        assert m.nv == 40
        self.m, self.d = m, d
        self.original = solver._cholesky_factorize_solve
        self.hits = 0

    def apply(self, m, d, ctx, output=None):
        wp.launch_tiled(solver.update_gradient_cholesky(m.nv), dim=d.nworld,
                        inputs=[ctx.grad, ctx.h, ctx.done],
                        outputs=[ctx.Mgrad if output is None else output], block_dim=64)

    @contextmanager
    def capture(self):
        def wrapped(m, d, ctx):
            if m is self.m and d is self.d:
                self.hits += 1
                return self.apply(m, d, ctx)
            return self.original(m, d, ctx)
        try:
            solver._cholesky_factorize_solve = wrapped
            yield self
        finally:
            solver._cholesky_factorize_solve = self.original
