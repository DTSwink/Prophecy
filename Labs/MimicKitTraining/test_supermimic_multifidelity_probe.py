import torch
from supermimic_multifidelity_probe import advantages,fit_coefficient,variance_ratio


def test_timeout_and_failure_bootstrap_without_reset_leakage():
    reward=torch.tensor([[1.,2.],[1000.,1000.]])
    value=torch.tensor([[3.,4.],[8.,9.]])
    next_value=torch.tensor([[10.,20.],[30.,40.]])
    failure=torch.tensor([[True,False],[False,False]])
    ended=torch.tensor([[True,True],[False,False]])
    adv=advantages(reward,value,next_value,failure,ended,gamma=.5,lam=1.)
    assert torch.equal(adv[0],torch.tensor([-2.,8.]))


def test_matched_independent_correction_preserves_mean_reduces_variance():
    # Analytic Gaussian score: E[a * (2*a+3)] = 2. Approximate model has
    # arbitrary incorrect scale/offset; its paired-minus-independent mean is0.
    rng=torch.Generator().manual_seed(31);n=200000
    a=torch.randn(n,generator=rng);other=torch.randn(n,4,generator=rng)
    high=(a*(2*a+3))[:,None]
    corrector=(a*(.7*a+2)-(other*(.7*other+2)).mean(1))[:,None]
    coefficient=fit_coefficient(high[:n//2],corrector[:n//2])
    after=high[n//2:]+coefficient*corrector[n//2:]
    assert abs(float(after.mean())-2)<.03
    assert variance_ratio(high[n//2:],corrector[n//2:],coefficient)<.3
    assert variance_ratio(high,corrector,0.)==1.


if __name__=='__main__':
    test_timeout_and_failure_bootstrap_without_reset_leakage()
    test_matched_independent_correction_preserves_mean_reduces_variance()
    print('2 multi-fidelity numerical checks passed')
