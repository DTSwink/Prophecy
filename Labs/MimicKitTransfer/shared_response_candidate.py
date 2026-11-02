"""Isolated matrix-response reuse candidate; frozen policies, no training."""
import importlib.util
import sys
from pathlib import Path


def load_candidate(source, output):
    text = Path(source).read_text()
    marker = 'wp.tile_assign(v,wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose(rhs))))'
    assert marker in text
    text = text.replace(marker, marker + '\n            wp.tile_assign(effective,wp.tile_cholesky_solve(effective,wp.tile_load(identity,shape=(nv,nv))))', 1)
    before, rest = text.split('def make_tiled_block_iteration', 1)
    before = before.replace('wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose(jac)))', 'wp.tile_matmul(jac,effective)')
    before = before.replace('wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose(spin_jac)))', 'wp.tile_matmul(spin_jac,effective)')
    Path(output).write_text(before + 'def make_tiled_block_iteration' + rest)
    spec = importlib.util.spec_from_file_location('shared_response_candidate_kernel', output)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def install(engine, source, output):
    module = load_candidate(source, output)
    p = engine.transfer_contact
    p.block_kernel = module.make_block_iteration(p.p.nv, p.p.nmotor, warm_start=True)
    p.retry_block_kernel = module.make_block_iteration(p.p.nv, p.p.nmotor, warm_start=True, retry=True)
    engine._build_graphs()
