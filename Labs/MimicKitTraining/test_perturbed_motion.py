"""Numerical contracts before any paid perturbed training is launched."""
from pathlib import Path
import math
import numpy as np
import torch
from perturbed_motion import MotionPrior, com2_velocity, yaw_matrix, yaw_velocities_preserving_com2, com2_failure, tracking_blend


def main():
    torch.set_num_threads(1)
    torch.manual_seed(57)
    dtype = torch.float64
    velocities = torch.randn(512, 15, 3, dtype=dtype)
    omega = torch.randn_like(velocities)
    angles = (torch.rand(512, dtype=dtype)*2-1)*math.pi/2
    rotation = yaw_matrix(angles)
    masses = torch.tensor([.3, .55, .15], dtype=dtype)
    ids = torch.tensor([0, 1, 2])
    turned, angular = yaw_velocities_preserving_com2(velocities, omega, rotation, ids, masses)
    torch.testing.assert_close(com2_velocity(turned[:, ids], masses), com2_velocity(velocities[:, ids], masses), atol=1e-14, rtol=1e-14)
    inverse = rotation.transpose(-1, -2)[:, None]
    torch.testing.assert_close((inverse@(turned-turned[:, :1]).unsqueeze(-1)).squeeze(-1), velocities-velocities[:, :1])
    torch.testing.assert_close((inverse@angular.unsqueeze(-1)).squeeze(-1), omega)
    assert torch.equal(turned[..., 2], velocities[..., 2])
    # Both possible lower thresholds are supported; launch awaits the user's choice.
    for lower in (.3, .7):
        target = torch.tensor([[2., 0.]], dtype=dtype)
        for speed, failed in ((lower*2-.001, True), (lower*2, False), (2., False), (3.4, False), (3.401, True)):
            assert bool(com2_failure(torch.tensor([[speed, 0.]], dtype=dtype), target, lower)) == failed
        for deg, failed in ((44.99, False), (45.01, True), (90., True), (180., True)):
            angle = math.radians(deg)
            assert bool(com2_failure(torch.tensor([[2*math.cos(angle), 2*math.sin(angle)]], dtype=dtype), target, lower)) == failed
    torch.testing.assert_close(tracking_blend(torch.tensor([0., 79., 80., 81., 110., 140., 141.])), torch.tensor([0., 0., 0., 1/60, .5, 1., 1.]))
    folder = Path(__file__).resolve().parents[2]/'Saved/MotionRegularizer-2x512'
    prior = MotionPrior(folder, 4, 'cpu')
    with np.load(folder/'example_windows.npz') as z:
        p, r = torch.tensor(z['positions']), torch.tensor(z['rotations'])
    prior.reset(torch.arange(4), p[:, 0], r[:, 0])
    assert not prior.cost().any()
    prior.append(p[:, 1], r[:, 1])
    assert not prior.cost().any()
    prior.append(p[:, 2], r[:, 2])
    torch.testing.assert_close(prior.cost(), prior.scorer(prior.encode(p, r)))
    prior.reset(torch.tensor([1, 3]), p[[1, 3], 0], r[[1, 3], 0])
    assert not prior.cost()[[1, 3]].any()
    assert (prior.valid == torch.tensor([3, 1, 3, 1])).all()
    assert all(not p.requires_grad for p in prior.scorer.parameters())
    print('PASS: COM2 XY preserved under yaw; local relative velocities unchanged; strict speed/direction gates; blend boundaries; exact portable AE scoring; partial reset history isolation.')


if __name__ == '__main__':
    main()
