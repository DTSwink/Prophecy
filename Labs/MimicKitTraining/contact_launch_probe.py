"""Isolated launch geometry tuning for the unchanged native contact Hessian kernel."""
from contextlib import contextmanager
import inspect, math
import warp as wp
from mujoco_warp._src import solver


class ContactLaunch:
    def __init__(self, model, data, factor=6, block_dim=256):
        self.factor = factor
        self.block_dim = block_dim
        self.dim_block = math.ceil(wp.get_device().sm_count * factor * 256 / model.dof_tri_row.size)
        self.nblocks = math.ceil(data.naconmax / self.dim_block)
        self.elements = model.dof_tri_row.size
        self.original = wp.launch
        self.signature = inspect.signature(wp.launch)
        self.hits = 0

    def launch(self, kernel, *args, **kwargs):
        if kernel is solver.update_gradient_JTCJ_dense:
            assert not args, 'Pinned contact kernel uses named launch arguments'
            kwargs = dict(kwargs)
            kwargs['dim'] = (self.dim_block, self.elements)
            inputs = list(kwargs['inputs'])
            assert len(inputs) == 18
            inputs[-2:] = [self.nblocks, self.dim_block]
            kwargs['inputs'] = inputs
            kwargs['block_dim'] = self.block_dim
            self.hits += 1
        return self.original(kernel, *args, **kwargs)

    @contextmanager
    def capture(self):
        self.hits = 0
        previous = wp.launch
        self.original = previous
        try:
            wp.launch = self.launch
            yield self
        finally:
            wp.launch = previous
