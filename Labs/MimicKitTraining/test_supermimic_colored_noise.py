import unittest
import torch
from supermimic_colored_noise import colored_sequence,ColoredSampler


class Checks(unittest.TestCase):
    def test_white_path_matches_independent_gaussian_exactly(self):
        first=torch.Generator().manual_seed(5);second=torch.Generator().manual_seed(5)
        x=colored_sequence((16,8,128),0.,generator=first)
        self.assertTrue(torch.equal(x,torch.randn((16,8,128),generator=second)))

    def test_gaussian_marginals_correlation_and_spectrum(self):
        x=colored_sequence((4000,256),.5,generator=torch.Generator().manual_seed(51))
        self.assertLess(abs(float(x.mean())),.02)
        self.assertLess(abs(float(x.square().mean())-1),.025)
        self.assertLess(abs(float(x[:,75].square().mean())-1),.06)
        self.assertLess(abs(float(x.pow(4).mean())-3),.15)
        self.assertGreater(float((x[:,1:]*x[:,:-1]).mean()),.2)
        psd=torch.fft.rfft(x).abs().square().mean(0)
        ratio=float(psd[4:9].mean()/psd[64:129].mean())
        self.assertGreater(ratio,3.);self.assertLess(ratio,5.)

    def test_sequence_continues_and_resamples_at_its_bound(self):
        s=ColoredSampler(.5,33,length=8);m=torch.zeros(2,3);std=torch.full_like(m,.075)
        values=[s.sample(m,std) for _ in range(9)]
        self.assertEqual(s.calls,9);self.assertEqual(s.index,1)
        self.assertFalse(torch.equal(values[0],values[-1]))
        self.assertEqual(s.audit()['length'],8)


if __name__=='__main__':unittest.main()
