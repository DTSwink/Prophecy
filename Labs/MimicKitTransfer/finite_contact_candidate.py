"""Diagnostic fixed-budget sequential contact solve, like Jolt's bounded solve.

This changes numerical accuracy; it is NOT an equivalent production replacement.
"""
from sequential_contact_adapter import SequentialContactAdapter

def install(engine,iterations,register=False,relaxation=.5):
    s=engine._solver;m=s.mjw_model;d=s.mjw_data
    p=SequentialContactAdapter(m,d,s.mj_model,engine._uefn_motors,iterations=iterations,
        allow_soft_limits=True,relaxation=relaxation,hard_limit_control=True,block_motors=False,
        manifolds=True,jolt_limit_axes=True)
    if register:
        from prepare_bounded_kernel import generate
        from staged_contact_candidate import module_from_file
        module=module_from_file('bounded_contact_gpu',generate())
        p.iterate_kernel=module.make_iteration(p.p.nv)
    m.transfer_contact_test=None;p.install();engine.transfer_contact=p;engine._build_graphs()
