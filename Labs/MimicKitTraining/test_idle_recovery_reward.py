import json
from pathlib import Path
import torch
from idle_recovery_reward import idle_recovery_reward

torch.manual_seed(8173)


def inputs(n=1):
    z=torch.zeros(n)
    return [z.clone(),z.clone(),torch.zeros(n,2),torch.zeros(n,2),
            z.clone(),z.clone(),z.clone(),torch.ones(n),torch.ones(n)]


def main():
    checks=[]
    x=inputs();r,c=idle_recovery_reward(*x)
    assert torch.equal(r,torch.ones_like(r)) and torch.count_nonzero(c)==0
    checks.append('ideal standing reward1 and zero costs')
    x=inputs(10000)
    for i in range(7):x[i]=torch.rand_like(x[i])*10**torch.randint(-4,7,x[i].shape).float()
    x[7]=torch.rand_like(x[7])*1.5;x[8]=torch.rand_like(x[8])*2-1
    r,c=idle_recovery_reward(*x)
    assert torch.isfinite(c).all() and (c>=0).all() and (r>=0).all() and (r<=1).all()
    assert torch.allclose(r,1-c.sum(-1),atol=2e-7)
    checks.append('10000 random states bounded and exact reward reconstruction')
    # All combination of style extremes: braking cannot lose to settle weighting.
    for mask in range(8):
        x=inputs(1001);x[0]=torch.linspace(0,9,1001)
        if mask&1:
            for i in (2,3,4):x[i].fill_(1e7)
        if mask&2:x[5].fill_(1e7)
        if mask&4:x[6].fill_(1e7)
        r,_=idle_recovery_reward(*x)
        assert (torch.diff(r)<=1e-7).all()
    checks.append('braking strictly preferred despite increasing style pressure')
    x=inputs(3);x[0]=torch.tensor([0.,.81,9.]);x[2][:,0]=.08
    r1,_=idle_recovery_reward(*x);x[2][:,0]=.04;r2,_=idle_recovery_reward(*x)
    assert (r2>r1).all()
    gains=(r2-r1).tolist()
    # Huge unrelated pose error does not hide the smoothness improvement.
    x[1].fill_(1e7);r3,_=idle_recovery_reward(*x);x[2][:,0]=.08;r4,_=idle_recovery_reward(*x)
    assert torch.allclose(r3-r4,r2-r1,atol=1e-7)
    checks.append('smoothness reward contrast independent of unrelated pose cost')
    x=inputs(3);x[7]=torch.tensor([.3,1.,1.]);x[8]=torch.tensor([1.,0.,1.]);x[0][2]=4
    r,_=idle_recovery_reward(*x)
    assert r[0]==0 and r[1]==0 and r[2]>0
    checks.append('stationary fallen states zero; fast upright recovery positive')
    x=inputs(2);x[0]=torch.tensor([0.,.0025]);x[6]=torch.tensor([0.,.0004]);r,_=idle_recovery_reward(*x)
    assert (r==1).all()
    checks.append('small speed and slip deadbands exact zero')
    x=inputs(2);x[2][1]=torch.tensor([.08,3.]);x[3][1]=torch.tensor([.04,1.]);x[4][1]=.02
    r,_=idle_recovery_reward(*x);assert r[0]>r[1]
    checks.append('quiet stopping preferred to same-speed reversal oscillation')
    x=inputs(2);r,_=idle_recovery_reward(*x,lowest_foot_height=torch.tensor([.0,.17]));torch.testing.assert_close(r,torch.tensor([1.,.25]))
    checks.append('airborne standing cannot earn grounded standing reward')
    report={'checks':checks,'passed':len(checks),'halving_foot_linear_gain_at_speeds_0_09_3':gains,
            'weights':[.55,.10,.15,.10,.10], 'module':'reward.py',
            'limitations':'Offline signal/formula tests, not evidence of improved learned policy.'}
    (Path(__file__).resolve().parents[2]/'Saved/MimicKitLocomotion/idle-recovery-20261028/cpu-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
