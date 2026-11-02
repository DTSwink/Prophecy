"""Finite/nonfinite equality gate for the isolated zero-product probe."""
from types import SimpleNamespace
import torch
import warp as wp
from mujoco_warp._src import types
from zero_quadratic_tiles_probe import ZeroQuadraticTiles


def check_edges():
    m = SimpleNamespace(is_sparse=True, nv=40, nv_pad=48)
    d = SimpleNamespace(nworld=64, njmax=128)
    candidate = ZeroQuadraticTiles(m, d)
    width = types.TILE_SIZE_JTDAJ_SPARSE
    blocks = (m.nv + width - 1) // width
    dim = (d.nworld, blocks*(blocks+1)//2)
    results = []
    for case in ['zero', 'quadratic', 'mixed', 'empty', 'large', 'nan_j',
                 'inf_j', 'negative_inf_j', 'nan_d_active', 'nan_d_padding']:
        nefc = torch.full((d.nworld,), 70, device='cuda', dtype=torch.int32)
        j = torch.randn((d.nworld, d.njmax, blocks*width), device='cuda')
        diagonal = torch.rand((d.nworld, d.njmax), device='cuda')
        state = torch.zeros((d.nworld, d.njmax), device='cuda', dtype=torch.int32)
        done = torch.zeros(d.nworld, device='cuda', dtype=torch.bool)
        done[-1] = True
        if case == 'quadratic':
            state.fill_(types.ConstraintState.QUADRATIC.value)
        if case == 'mixed':
            state[:, ::3] = types.ConstraintState.QUADRATIC.value
        if case == 'empty':
            nefc.zero_()
        if case == 'large':
            j.mul_(1e20)
        if case in ['nan_j', 'inf_j', 'negative_inf_j']:
            j[:, 2, 4] = {'nan_j': float('nan'), 'inf_j': float('inf'),
                          'negative_inf_j': -float('inf')}[case]
        if case in ['nan_d_active', 'nan_d_padding']:
            index = 2 if case == 'nan_d_active' else 75
            diagonal[:, index] = float('nan')
            state[:, index] = types.ConstraintState.QUADRATIC.value
        tensors = [nefc, j, diagonal, state, done]
        inputs = [wp.from_torch(v) for v in tensors]
        expected = wp.zeros((d.nworld, m.nv_pad, m.nv_pad), dtype=float)
        actual = wp.zeros_like(expected)
        wp.to_torch(expected)[-1].fill_(73.)
        wp.to_torch(actual)[-1].fill_(73.)
        wp.launch_tiled(candidate.kernel, dim=dim, inputs=inputs,
                        outputs=[expected], block_dim=32)
        with candidate.capture():
            wp.launch_tiled(candidate.kernel, dim=dim, inputs=inputs,
                            outputs=[actual], block_dim=32)
        wp.synchronize()
        torch.testing.assert_close(wp.to_torch(actual), wp.to_torch(expected),
                                   rtol=0, atol=0, equal_nan=True)
        results.append(dict(case=case, equal_values_and_nonfinite_classification=True,
                            done_world_unchanged=bool((wp.to_torch(actual)[-1] == 73.).all())))
    return results
