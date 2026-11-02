"""Specialize supported contact dimensions and reuse native dense-Jacobian fusion."""
from contextlib import contextmanager
import inspect
import numpy as np
import warp as wp
from mujoco_warp._src import solver
from contact_condim3_probe import contact_hessian_condim3


class ContactStages:
    def __init__(self, model, data, native_model, static_cone=False, fused_jv=False):
        assert set(np.unique(native_model.geom_condim)).issubset({1,3})
        assert set(np.unique(native_model.pair_dim)).issubset({1,3})
        assert model.nv==40
        assert data.efc.J.shape[1]>=data.njmax and data.efc.J.shape[2]==model.nv_pad
        assert not solver.SPARSE_CONSTRAINT_JACOBIAN
        assert not model.opt.ls_parallel
        self.static_cone=static_cone;self.fused_jv=fused_jv
        self.original=wp.launch;self.signature=inspect.signature(wp.launch)
        self.original_linesearch=solver._linesearch
        self.hits=0

    def launch(self,kernel,*args,**kwargs):
        if kernel is solver.update_gradient_JTCJ_dense and self.static_cone:
            kernel=contact_hessian_condim3
            self.hits+=1
        return self.original(kernel,*args,**kwargs)

    def linesearch(self,m,d,ctx,cost):
        # Preserve the sparse mass-matrix product; only the Jacobian is dense.
        solver.support.mul_m(m,d,ctx.mv,ctx.search,skip=ctx.done)
        solver._linesearch_iterative(m,d,ctx,True)

    @contextmanager
    def capture(self):
        self.hits=0
        previous=wp.launch
        self.original=previous
        previous_linesearch=solver._linesearch
        try:
            wp.launch=self.launch
            if self.fused_jv:solver._linesearch=self.linesearch
            yield self
        finally:
            solver._linesearch=previous_linesearch
            wp.launch=previous
