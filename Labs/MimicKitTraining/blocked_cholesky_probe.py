"""Exact same blocked solve, with 64 rather than 32 execution threads."""
from contextlib import contextmanager
import warp as wp
from mujoco_warp._src import solver, types

class BlockedCholesky:
    def __init__(self, m, d):
        assert m.nv == 40
        self.m, self.d = m, d
        self.original = solver._cholesky_factorize_solve
        self.hfactor = wp.zeros((d.nworld,m.nv_pad,m.nv_pad),dtype=float)

    def apply(self, m, d, ctx, output=None):
        wp.launch(solver.padding_h,dim=(d.nworld,m.nv_pad-m.nv),inputs=[m.nv,ctx.done],outputs=[ctx.h])
        result=ctx.Mgrad if output is None else output
        wp.launch_tiled(solver.update_gradient_cholesky_blocked(types.TILE_SIZE_JTDAJ_DENSE,m.nv_pad),
                        dim=d.nworld, inputs=[ctx.done,ctx.grad.reshape((d.nworld,ctx.grad.shape[1],1)),ctx.h,self.hfactor],
                        outputs=[result.reshape((d.nworld,result.shape[1],1))],block_dim=64)

    @contextmanager
    def capture(self):
        def wrapped(m,d,ctx):
            return self.apply(m,d,ctx) if m is self.m and d is self.d else self.original(m,d,ctx)
        try:
            solver._cholesky_factorize_solve=wrapped
            yield self
        finally:
            solver._cholesky_factorize_solve=self.original
