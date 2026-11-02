"""Skip Newton search directions that cannot be consumed after convergence.

The gradient and cost are unchanged. The existing solve_done kernel runs before
Hessian assembly, so converged worlds skip only private scratch calculations.
This is an isolated candidate, restricted to the pinned Newton/elliptic solver.
"""
import inspect
from contextlib import contextmanager
from mujoco_warp._src import solver, types
import warp as wp


class EarlyDone:
    def __init__(self, model):
        assert model.opt.solver == types.SolverType.NEWTON
        assert model.opt.cone == types.ConeType.ELLIPTIC
        assert model.opt.graph_conditional
        assert not solver.SPARSE_CONSTRAINT_JACOBIAN
        self.original = solver._solver_iteration
        source = inspect.getsource(solver._update_gradient)
        signature = 'def _update_gradient(m: types.Model, d: types.Data, ctx: SolverContext):'
        assert signature in source
        source = source.replace(signature, 'def gradient_before_done(m: types.Model, d: types.Data, ctx: SolverContext, nsolving):', 1)
        marker = '  if m.opt.solver == types.SolverType.CG:'
        assert source.count(marker) == 1
        insertion = '''  wp.launch(
    solve_done, dim=d.nworld,
    inputs=[m.nv, m.opt.tolerance, m.opt.iterations, m.stat.meaninertia,
            ctx.grad_dot, ctx.cost, ctx.prev_cost, ctx.done],
    outputs=[d.solver_niter, nsolving, ctx.done])

'''
        source = source.replace(marker, insertion + marker, 1)
        namespace = dict(vars(solver))
        exec(compile(source, '<early-done-gradient>', 'exec'), namespace)
        self.gradient = namespace['gradient_before_done']

    def iteration(self, m, d, ctx, step_size_cost, nsolving):
        solver._linesearch(m, d, ctx, step_size_cost)
        solver._update_constraint(m, d, ctx, track_changes=False)
        self.gradient(m, d, ctx, nsolving)
        wp.launch(solver.solve_zero_search_dot, dim=d.nworld,
                  inputs=[ctx.done], outputs=[ctx.search_dot])
        wp.launch(solver.solve_search_update, dim=(d.nworld, m.nv),
                  inputs=[m.opt.solver, ctx.Mgrad, ctx.search, ctx.beta, ctx.done],
                  outputs=[ctx.search, ctx.search_dot])

    @contextmanager
    def capture(self):
        try:
            solver._solver_iteration = self.iteration
            yield self
        finally:
            solver._solver_iteration = self.original
