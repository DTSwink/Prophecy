"""CPU numerical checks for the added velocity objective. No training."""
import torch
from flat_com import flat_com_velocity, expanded_band, band_loss


def test():
    reference = torch.tensor([[-3., 2.], [-1., 4.]])
    bounds = expanded_band(reference, .1)
    torch.testing.assert_close(bounds, torch.tensor([[-3.2, 1.8], [-.8, 4.2]]))
    v = torch.tensor([[-3.2, 1.8], [-.8, 4.2], [-2., 3.], [-3.7, 4.7]], requires_grad=True)
    loss = band_loss(v, bounds)
    torch.testing.assert_close(loss, torch.tensor([0., 0., 0., .25]))
    loss.sum().backward()
    torch.testing.assert_close(v.grad[:3], torch.zeros(3, 2))
    assert v.grad[-1, 0] < 0 and v.grad[-1, 1] > 0
    # A constant/signed axis keeps its value, instead of padding the speed
    # itself and producing inverted ranges when moving backwards.
    constant = expanded_band(torch.tensor([[-2., 0.], [-2., 0.]]), .1)
    torch.testing.assert_close(constant, torch.tensor([[-2., 0.], [-2., 0.]]))
    torch.testing.assert_close(flat_com_velocity(torch.tensor([[[1., 2., 999.], [3., 6., -999.]]]),
        torch.tensor([.25, .75])), torch.tensor([[2.5, 5.]]))
    # Excluded limbs cannot affect the COM, including arbitrary arm speeds.
    full = torch.randn(4, 15, 3); ids = torch.tensor([0, 1, 2, 9, 10, 11, 12, 13, 14])
    weights = torch.arange(1, 10).float(); weights /= weights.sum()
    before = flat_com_velocity(full[:, ids], weights)
    full[:, 3:9] *= 1e6
    torch.testing.assert_close(before, flat_com_velocity(full[:, ids], weights))
    print('flat COM contracts passed: bounds, signs, gradients, masses, arm exclusion, Z exclusion')


if __name__ == '__main__': test()
