"""Closed-loop forecast must reproduce recorded exploration and reset masks."""
from types import SimpleNamespace
import unittest
import torch
from supermimic_fit_dose import forecast


class ForecastTest(unittest.TestCase):
    def test_exact_model_and_matched_noise_exclude_reset_rows(self):
        class Actor:
            def eval_actor(self,obs):return SimpleNamespace(mode=.1*obs[:,:1]+.01*obs[:,1:2])
            def eval_phase(self,obs):return obs[:,1:3].flip(-1)
        class World:
            def __init__(self,bias=0.):self.bias=bias
            def step(self,x,a):return x+a+self.bias
        actor=Actor();world=World();ctx=SimpleNamespace(a=SimpleNamespace(_model=actor),
            e=SimpleNamespace(_gaits=torch.tensor([0.])),low=-10.,high=10.,
            obs=lambda x,m,p:torch.cat((x,p),-1))
        x=torch.zeros(4,1);phase=torch.tensor([[1.,0.]]).repeat(4,1);rows=[]
        for tick in range(32):
            mean=actor.eval_actor(ctx.obs(x,None,phase)).mode
            raw=mean+torch.tensor([.01,-.02,.03,-.04])[:,None]
            nxt=world.step(x,raw);next_phase=phase.flip(-1)
            done=torch.tensor([tick==3,False,False,False])
            rows.append(dict(x=x,next_x=nxt,a=raw,raw_a=raw,mean_a=mean,phase=phase,
                next_phase=next_phase,motion=torch.zeros(4,dtype=torch.long),
                pert=torch.ones(4,dtype=torch.bool),done=done))
            x=nxt.clone();phase=next_phase
            if tick==3:x[0]=10.  # Counterfactual following a real reset must be excluded.
        batch={k:torch.stack([r[k] for r in rows]) for k in rows[0]}
        result=forecast(ctx,world,batch,True)
        for h,count in [(1,4),(8,3),(32,3)]:
            q=result['h'+str(h)]['perturbed_loco']
            self.assertEqual(q['rows'],count)
            self.assertLess(q['state_nse'],1e-10)
            self.assertLess(q['next_action_rmse'],1e-6)
        biased=forecast(ctx,World(.01),batch,True)
        self.assertGreater(biased['h32']['all']['state_nse'],biased['h1']['all']['state_nse'])


if __name__=='__main__':unittest.main()
