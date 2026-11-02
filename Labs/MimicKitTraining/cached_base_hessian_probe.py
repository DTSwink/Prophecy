"""Probe-only cache of unchanged quadratic Hessian contributions within a solve.

The native kernels populate the cache. It is refreshed unconditionally at the
start of every solve and whenever QUADRATIC membership changes. Elliptic cone
terms are always recomputed by the original solver. Audit runs the uncached
native kernels alongside the candidate before the cone contribution is added.
"""
from contextlib import contextmanager
import warp as wp
from mujoco_warp._src import solver, types


@wp.kernel(enable_backward=False)
def refresh_mask(nefc: wp.array(dtype=int), state: wp.array2d(dtype=int),
                 done: wp.array(dtype=bool), initial: bool,
                 previous: wp.array2d(dtype=int), skip: wp.array(dtype=bool)):
    w = wp.tid()
    if done[w]:
        skip[w] = True
        return
    changed = initial
    for k in range(nefc[w]):
        quadratic = int(state[w, k] == types.ConstraintState.QUADRATIC.value)
        if previous[w, k] != quadratic:
            changed = True
        previous[w, k] = quadratic
    skip[w] = not changed


@wp.kernel(enable_backward=False)
def copy_active(done: wp.array(dtype=bool), source: wp.array3d(dtype=float),
                target: wp.array3d(dtype=float)):
    w, i, j = wp.tid()
    if not done[w]:
        target[w, i, j] = source[w, i, j]


@wp.kernel(enable_backward=False)
def check_exact(done: wp.array(dtype=bool), skip: wp.array(dtype=bool),
                actual: wp.array3d(dtype=float), reference: wp.array3d(dtype=float),
                counts: wp.array2d(dtype=int), maximum: wp.array(dtype=float)):
    w, i, j = wp.tid()
    if done[w]:
        return
    a = actual[w, i, j]
    b = reference[w, i, j]
    if a != b:
        wp.atomic_add(counts, w, 1, 1)
        wp.atomic_max(maximum, w, wp.abs(a - b))
    if not wp.isfinite(a) or not wp.isfinite(b):
        wp.atomic_add(counts, w, 2, 1)
    if i == 0 and j == 0:
        wp.atomic_add(counts, w, 0, actual.shape[1] * actual.shape[2])
        wp.atomic_add(counts, w, 3, int(skip[w]))
        wp.atomic_add(counts, w, 4, 1)


class CachedBaseHessian:
    def __init__(self, m, d):
        assert m.is_sparse and not solver.SPARSE_CONSTRAINT_JACOBIAN
        assert m.opt.solver == types.SolverType.NEWTON
        assert m.opt.cone == types.ConeType.ELLIPTIC
        self.m, self.d = m, d
        self.kernel = solver.update_gradient_JTDAJ_sparse_tiled(
            types.TILE_SIZE_JTDAJ_SPARSE, d.njmax)
        self.mass_kernel = solver.update_gradient_set_h_qM_lower_sparse
        self.original = wp.launch
        self.original_tiled = wp.launch_tiled
        self.audit = False
        self.resources = []
        self.entries = {}
        self.hits = 0
        self.mass_hits = 0
        self.counts = wp.zeros((d.nworld, 5), dtype=int)
        self.maximum = wp.zeros(d.nworld, dtype=float)

    def tiled(self, kernel, *args, **kwargs):
        if kernel is not self.kernel:
            return self.original_tiled(kernel, *args, **kwargs)
        assert not args
        inputs = list(kwargs['inputs'])
        assert len(inputs) == 5
        h = kwargs['outputs'][0]
        key = h.ptr
        initial = key not in self.entries
        if initial:
            entry = dict(base=wp.zeros_like(h), previous=wp.zeros_like(inputs[3]),
                         skip=wp.empty_like(inputs[4]), done=inputs[4], h=h)
            if self.audit:
                entry['reference'] = wp.zeros_like(h)
            self.entries[key] = entry
            self.resources.append(entry)
        entry = self.entries[key]
        assert entry['done'].ptr == inputs[4].ptr
        self.original(refresh_mask, dim=self.d.nworld,
                      inputs=[inputs[0], inputs[3], inputs[4], initial,
                              entry['previous'], entry['skip']])
        changed = dict(kwargs, inputs=[*inputs[:4], entry['skip']],
                       outputs=[entry['base']])
        self.original_tiled(kernel, **changed)
        if self.audit:
            self.original_tiled(kernel, **dict(kwargs, outputs=[entry['reference']]))
        self.hits += 1

    def launch(self, kernel, *args, **kwargs):
        if kernel is not self.mass_kernel:
            return self.original(kernel, *args, **kwargs)
        assert not args
        inputs = list(kwargs['inputs'])
        h = kwargs['outputs'][0]
        entry = self.entries[h.ptr]
        assert len(inputs) == 4 and inputs[3].ptr == entry['done'].ptr
        self.original(kernel, **dict(kwargs, inputs=[*inputs[:3], entry['skip']],
                                     outputs=[entry['base']]))
        self.original(copy_active, dim=h.shape,
                      inputs=[entry['done'], entry['base'], h])
        if self.audit:
            self.original(kernel, **dict(kwargs, outputs=[entry['reference']]))
            self.original(check_exact, dim=h.shape,
                          inputs=[entry['done'], entry['skip'], h, entry['reference'],
                                  self.counts, self.maximum])
        self.mass_hits += 1

    @contextmanager
    def capture(self):
        self.entries = {}
        self.hits = self.mass_hits = 0
        previous, previous_tiled = wp.launch, wp.launch_tiled
        self.original, self.original_tiled = previous, previous_tiled
        try:
            wp.launch, wp.launch_tiled = self.launch, self.tiled
            yield self
        finally:
            wp.launch, wp.launch_tiled = previous, previous_tiled
