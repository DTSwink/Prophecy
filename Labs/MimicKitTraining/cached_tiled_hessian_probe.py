"""Probe: reuse native quadratic tiles without a separate matrix-copy pass."""
import inspect
from contextlib import contextmanager
import warp as wp
from mujoco_warp._src import solver, types
from cached_base_hessian_probe import refresh_mask, check_exact


@wp.func
def quadratic(state: int):
    return int(state == types.ConstraintState.QUADRATIC.value)


@wp.func
def different(a: int, b: int):
    return int(a != b)


@wp.func
def active(index: int, count: int):
    return int(index < count)


@wp.kernel(enable_backward=False)
def refresh_tiled(nefc: wp.array(dtype=int), state: wp.array2d(dtype=int),
                  done: wp.array(dtype=bool), initial: bool,
                  previous: wp.array2d(dtype=int), skip: wp.array(dtype=bool)):
    w = wp.tid()
    if done[w]:
        skip[w] = True
        return
    changed = int(0)
    for offset in range(0, nefc[w], 32):
        now = wp.tile_map(quadratic, wp.tile_load(state[w], shape=32, offset=offset))
        old = wp.tile_load(previous[w], shape=32, offset=offset)
        delta = wp.tile_map(different, now, old)
        enabled = wp.tile_map(active, wp.tile_arange(32, dtype=int),
                              wp.tile_ones(shape=32, dtype=int) * (nefc[w] - offset))
        changed += wp.tile_extract(wp.tile_sum(wp.tile_map(wp.mul, delta, enabled)), 0)
        wp.tile_store(previous[w], now, offset=offset)
    skip[w] = not (initial or changed > 0)


class CachedTiledHessian:
    def __init__(self, m, d):
        assert m.is_sparse and not solver.SPARSE_CONSTRAINT_JACOBIAN
        assert m.opt.solver == types.SolverType.NEWTON
        assert m.opt.cone == types.ConeType.ELLIPTIC
        self.m, self.d = m, d
        self.kernel = solver.update_gradient_JTDAJ_sparse_tiled(
            types.TILE_SIZE_JTDAJ_SPARSE, d.njmax)
        source = inspect.getsource(solver.update_gradient_JTDAJ_sparse_tiled)
        source = source.replace('@cache_kernel\n', '', 1)
        source = source.replace('def update_gradient_JTDAJ_sparse_tiled(',
                                'def cached_JTDAJ_sparse_tiled(', 1)
        marker = '    ctx_h_out: wp.array3d(dtype=float),'
        assert source.count(marker) == 1
        source = source.replace(marker,
            '    reuse_in: wp.array(dtype=bool),\n'
            '    cached_in: wp.array3d(dtype=float),\n' + marker, 1)
        marker = '    sum_val = wp.tile_zeros(shape=(TILE_SIZE, TILE_SIZE), dtype=wp.float32)'
        assert source.count(marker) == 1
        source = source.replace(marker, '''    if reuse_in[worldid]:
      value = wp.tile_load(cached_in[worldid], shape=(TILE_SIZE, TILE_SIZE),
                           offset=(offset_i, offset_j), bounds_check=True)
      wp.tile_store(ctx_h_out[worldid], value, offset=(offset_i, offset_j), bounds_check=True)
      return

''' + marker, 1)
        marker = '    wp.tile_store(ctx_h_out[worldid], sum_val, offset=(offset_i, offset_j), bounds_check=True)'
        assert source.count(marker) == 1
        source = source.replace(marker, marker + '\n'
            '    wp.tile_store(cached_in[worldid], sum_val, offset=(offset_i, offset_j), bounds_check=True)', 1)
        # Warp obtains the kernel body from its Python source file. Keep this
        # generated source in the isolated probe directory for reproducibility.
        from pathlib import Path
        import importlib.util
        generated = Path(__file__).with_name('cached_tiled_generated.py')
        license_header = Path(solver.__file__).read_text().split('import dataclasses', 1)[0]
        generated.write_text(license_header + 'import warp as wp\nfrom mujoco_warp._src.solver import sqrt,state_check,active_check\n' + source)
        spec = importlib.util.spec_from_file_location('cached_tiled_generated', generated)
        module = importlib.util.module_from_spec(spec)
        import sys
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.new_kernel = module.cached_JTDAJ_sparse_tiled(types.TILE_SIZE_JTDAJ_SPARSE, d.njmax)
        self.original = wp.launch_tiled
        self.audit = False
        self.resources = []
        self.entries = {}
        self.hits = 0
        self.counts = wp.zeros((d.nworld, 5), dtype=int)
        self.maximum = wp.zeros(d.nworld, dtype=float)

    def tiled(self, kernel, *args, **kwargs):
        if kernel is not self.kernel:
            return self.original(kernel, *args, **kwargs)
        assert not args
        inputs = list(kwargs['inputs'])
        assert len(inputs) == 5
        h = kwargs['outputs'][0]
        initial = h.ptr not in self.entries
        if initial:
            entry = dict(base=wp.zeros_like(h), previous=wp.zeros_like(inputs[3]),
                         skip=wp.empty_like(inputs[4]), done=inputs[4], h=h)
            if self.audit:
                entry['reference'] = wp.zeros_like(h)
            self.entries[h.ptr] = entry
            self.resources.append(entry)
        entry = self.entries[h.ptr]
        assert entry['done'].ptr == inputs[4].ptr and entry['h'] is h
        self.original(refresh_tiled, dim=self.d.nworld, block_dim=32,
                      inputs=[inputs[0], inputs[3], inputs[4], initial,
                              entry['previous'], entry['skip']])
        self.original(self.new_kernel,
                      **dict(kwargs, inputs=[*inputs, entry['skip'], entry['base']]))
        if self.audit:
            self.original(kernel, **dict(kwargs, outputs=[entry['reference']]))
            wp.launch(check_exact, dim=h.shape,
                      inputs=[entry['done'], entry['skip'], h, entry['reference'],
                              self.counts, self.maximum])
        self.hits += 1

    @contextmanager
    def capture(self):
        self.entries = {}
        self.hits = 0
        previous = wp.launch_tiled
        self.original = previous
        try:
            wp.launch_tiled = self.tiled
            yield self
        finally:
            wp.launch_tiled = previous
