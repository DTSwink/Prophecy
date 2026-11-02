"""Check the gradient diagnostic against an analytically solvable system."""
import types
import unittest
import torch
from supermimic_gradient_fidelity import rollout_advice


class FidelityTests(unittest.TestCase):
    def test_exact_model_recovers_known_gradients_and_biased_model_separates_forward_error(self):
        n=2;horizon=3;phase=torch.tensor([[1.,0.]]).repeat(n,1)
        x=torch.zeros(n,146);x[:,1]=1;x[:,6]=1
        env=types.SimpleNamespace(_gaits=torch.zeros(1),_body_com=torch.zeros(1,15,3),
                                  _perturb_cfg={'loco_failure_penalty':100.})
        class Actor:
            def eval_critic(self,obs):return torch.zeros(len(obs),1)
        ctx=types.SimpleNamespace(e=env,a=types.SimpleNamespace(_model=Actor()),
            mean=torch.zeros(146),std=torch.ones(146),low=-torch.ones(34),high=torch.ones(34))
        ctx.physical=lambda obs:obs[:,:146]
        ctx.obs=lambda x,m,p:x
        ctx.policy=lambda x,m,p:(x.new_zeros(len(x),34),x.new_zeros(len(x),34),phase)
        ctx.clock_phase=lambda m,t:phase
        ctx.head_context=lambda m,p,a,pert:torch.zeros(len(m),1)
        class World:
            bias=0.
            def step(self,x,a):return torch.cat((x[:,:1]+a[:,:1]+self.bias,x[:,1:]),-1)
            def terminal(self,x):return torch.full((len(x),1),-10.)
        class Score:
            def __call__(self,h,xy,m,p,age,t,pert):return 1-(1-h[:,-1,0]).square(),None
            def failure(self,x,xy,m,a,p):return torch.zeros(len(x),dtype=torch.bool),torch.zeros(len(x))
        init=dict(obs=torch.cat((x,phase),-1),history=x[:,None].repeat(1,3,1),
            xy_history=torch.zeros(n,3,2),motion=torch.zeros(n,dtype=torch.long),
            pert=torch.ones(n,dtype=torch.bool),valid=torch.ones(n,dtype=torch.bool),
            age=torch.zeros(n),times=torch.zeros(n))
        traj=[dict(mean=torch.zeros(n,34),raw=torch.zeros(n,34),phase=phase,x=x,
            xy=torch.zeros(n,2),done=torch.zeros(n,dtype=torch.bool),fail=torch.zeros(n,dtype=torch.bool),
            reward=torch.zeros(n)) for _ in range(horizon)]
        wm=World();scorer=Score();expected=2*(1+.99+.99**2)
        for anchored in [False,True]:
            d,objectives,quality=rollout_advice(ctx,wm,scorer,init,traj,anchored)
            g=torch.autograd.grad(objectives['dense'].sum(),d,retain_graph=True)[0]
            torch.testing.assert_close(g[:,0],torch.full((n,),expected))
            self.assertTrue(bool((g[:,1:]==0).all()))
            g1=torch.autograd.grad(objectives['h1_dense'].sum(),d)[0]
            torch.testing.assert_close(g1[:,0],torch.full((n,),2.))
            self.assertEqual(quality['h1']['state_nse'],0.)
        wm.bias=.1
        d,a,qa=rollout_advice(ctx,wm,scorer,init,traj,True)
        _,f,qf=rollout_advice(ctx,wm,scorer,init,traj,False)
        self.assertEqual(qa['h1']['state_nse'],0.)
        self.assertGreater(qf['h1']['state_nse'],0.)
        torch.testing.assert_close(a['dense'],torch.zeros(n))
        self.assertTrue(bool((f['dense']>0).all()))
        g=torch.autograd.grad(a['dense'].sum(),d)[0]
        torch.testing.assert_close(g[:,0],torch.full((n,),expected))


if __name__=='__main__':unittest.main()
