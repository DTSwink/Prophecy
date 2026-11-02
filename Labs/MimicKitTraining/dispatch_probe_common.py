"""Rebuild probe graphs while retaining every installed production optimization.

Probe-only utility. It is not imported by training or deployed packages.
"""
from contextlib import ExitStack


def build_variant_graph(engine, *candidates):
    sparse, factor = engine._dispatch_resources
    early = engine._converged_newton_resource
    cached48 = getattr(engine, '_cached48_resource', None)
    before = dict(sparse.hits)
    factor_before = factor.hits
    with ExitStack() as stack:
        for resource in [sparse, factor, early]:
            stack.enter_context(resource.capture())
        if cached48 is not None:
            stack.enter_context(cached48.capture())
        for candidate in candidates:
            stack.enter_context(candidate.capture())
        engine._build_graphs()
    report = dict(sparse={key:sparse.hits[key]-before[key] for key in before},
                  factor=factor.hits-factor_before,
                  cached48=cached48.hits if cached48 is not None else None)
    assert report['sparse'] == {'velocity':8, 'derivative':8}, report
    assert report['factor'] == 16, report
    assert report['cached48'] == (16 if cached48 is not None else None), report
    return engine._graph, report
