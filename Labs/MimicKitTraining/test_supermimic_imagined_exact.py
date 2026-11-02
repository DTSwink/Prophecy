import types
import unittest
from unittest.mock import patch
import torch
from supermimic_imagined_exact import survival_objective,update,hard_forward_failure,phase_feedback,direct_tracking_reward
from supermimic_exact_reward import com2_failure_surrogate


class ImaginedTests(unittest.TestCase):
    def test_direct_gradient_keeps_rewards_and_failure_derivative(self):
        terms=torch.tensor([[.1,.2],[10.,20.]],requires_grad=True)
        reward=(1+terms.sum(-1)).reciprocal()
        direct=direct_tracking_reward(reward,terms,.25)
        torch.testing.assert_close(direct,reward,rtol=0,atol=0)
        gradient=torch.autograd.grad(direct.sum(),terms)[0]
        torch.testing.assert_close(gradient,torch.full_like(terms,-.25))
        # Critic targets and failure-survival gradients retain the actual reward.
        fail=torch.tensor([[.1],[.2]],requires_grad=True)
        values=torch.ones(3,1)
        timeout=torch.zeros(2,1,dtype=torch.bool)
        direct=direct_tracking_reward(reward,terms,.25)
        a=survival_objective(direct[:,None]-100*fail,fail,timeout,values)[0]
        b=survival_objective(reward[:,None]-100*fail,fail,timeout,values)[0]
        torch.testing.assert_close(a,b,rtol=0,atol=0)
        ga=torch.autograd.grad(a.sum(),fail,retain_graph=True)[0]
        gb=torch.autograd.grad(b.sum(),fail)[0]
        torch.testing.assert_close(ga,gb,rtol=0,atol=0)

    def test_phase_detach_preserves_forward_and_normal_supervision(self):
        prediction=torch.tensor([[.8,.2],[.4,.6]],requires_grad=True)
        clock=torch.tensor([[1.,0.],[0.,1.]])
        pert=torch.tensor([True,False])
        ordinary=phase_feedback(prediction,clock,pert)
        detached=phase_feedback(prediction,clock,pert,True)
        torch.testing.assert_close(ordinary,detached,rtol=0,atol=0)
        self.assertFalse(detached.requires_grad)
        task_gradient=torch.autograd.grad(ordinary[:,1].sum(),prediction)[0]
        self.assertGreater(float(task_gradient[0].norm()),0.)
        self.assertEqual(float(task_gradient[1].norm()),0.)
        supervision=((prediction-clock).square().mean(-1)*(~pert)).mean()
        gradient=torch.autograd.grad(supervision,prediction)[0]
        self.assertEqual(float(gradient[0].norm()),0.)
        self.assertGreater(float(gradient[1].norm()),0.)

    def test_matching_target_has_no_terminal_tax_and_keeps_surrogate_gradient(self):
        velocity=torch.tensor([[1.,0.],[.8,.5]],requires_grad=True)
        target=torch.tensor([[1.,0.],[1.,0.]])
        hard,soft=com2_failure_surrogate(velocity,target)
        fixed=hard_forward_failure(hard,soft)
        self.assertFalse(bool(hard.any()))
        self.assertGreater(float(100*soft[0].detach()),.28)
        torch.testing.assert_close(fixed,torch.zeros(2))
        smooth_gradient=torch.autograd.grad(soft.sum(),velocity,retain_graph=True)[0]
        actual_gradient=torch.autograd.grad(fixed.sum(),velocity)[0]
        torch.testing.assert_close(actual_gradient,smooth_gradient)
        self.assertGreater(float(actual_gradient.abs().sum()),0.)

    def test_hard_forward_critic_target_has_no_false_survival_discount(self):
        soft=torch.full((3,1),.1,requires_grad=True)
        fail=hard_forward_failure(torch.zeros(3,1,dtype=torch.bool),soft)
        rewards=torch.ones(3,1)-100*fail
        values=torch.full((4,1),10.)
        total,weights,continuation,timeout=survival_objective(rewards,fail,torch.zeros(3,1,dtype=torch.bool),values,.9)
        torch.testing.assert_close(total.detach(),torch.tensor([1+.9+.9**2+.9**3*10]))
        torch.testing.assert_close(continuation.detach(),torch.ones(3,1))

    def test_soft_survival_matches_explicit_recurrence_and_finite_difference(self):
        reward=torch.tensor([[1.],[2.],[3.]],dtype=torch.float64)
        failure=torch.tensor([[.1],[.2],[.3]],dtype=torch.float64,requires_grad=True)
        timeout=torch.zeros(3,1,dtype=torch.bool)
        values=torch.arange(4.,dtype=torch.float64)[:,None]
        result,*_=survival_objective(reward,failure,timeout,values,.9)
        expected=1+.9*.9*2+.9**2*.9*.8*3+.9**3*.9*.8*.7*3
        self.assertAlmostEqual(float(result.detach()),expected)
        derivative=torch.autograd.grad(result.sum(),failure)[0]
        eps=1e-5
        plus=failure.detach().clone();minus=plus.clone();plus[1]+=eps;minus[1]-=eps
        fd=(survival_objective(reward,plus,timeout,values,.9)[0]-
            survival_objective(reward,minus,timeout,values,.9)[0])/(2*eps)
        torch.testing.assert_close(derivative[1],fd)

    def test_failure_counts_terminal_penalty_once_and_no_bootstrap(self):
        r=torch.tensor([[1.],[-99.],[10000.]])
        f=torch.tensor([[0.],[1.],[0.]])
        value=torch.full((4,1),10000.)
        total,weights,*_=survival_objective(r,f,torch.zeros(3,1,dtype=torch.bool),value,.9)
        torch.testing.assert_close(total,torch.tensor([1-.9*99]))
        torch.testing.assert_close(weights[:,0],torch.tensor([1.,1.,0.]))

    def test_timeout_uses_pre_reset_value_and_cuts_subsequent_rewards(self):
        r=torch.tensor([[1.],[2.],[10000.]])
        timeout=torch.tensor([[False],[True],[False]])
        value=torch.tensor([[5.],[6.],[7.],[10000.]])
        total,*_=survival_objective(r,torch.zeros_like(r),timeout,value,.9)
        torch.testing.assert_close(total,torch.tensor([1+.9*(2+.9*7)]))

    def test_real_update_changes_actor_and_critic_but_not_dynamics(self):
        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__();self.motor=torch.nn.Parameter(torch.tensor(.01))
                self.value=torch.nn.Linear(146,1,bias=False)
                torch.nn.init.zeros_(self.value.weight)
                self._critic_layers=torch.nn.Sequential(self.value)
                self._critic_out=torch.nn.Identity()
            def get_actor_params(self):return [self.motor]
            def get_critic_params(self):return self.value.parameters()
            def eval_actor(self,obs):return types.SimpleNamespace(mode=self.motor.expand(len(obs),34),stddev=torch.full((len(obs),34),.075))
            def eval_critic(self,obs):return self.value(obs)
        class World(torch.nn.Module):
            def __init__(self):
                super().__init__();self.weight=torch.nn.Parameter(torch.tensor(1.))
                self.terminal=torch.nn.Linear(147,1)
            def step(self,x,a):return torch.cat((x[:,:1]+self.weight*a[:,:1],x[:,1:]),-1)
        model=Model();wm=World();n=4
        agent=types.SimpleNamespace(_model=model,_phase_weight=0.,_action_bound_weight=0.)
        env=types.SimpleNamespace(_body_com=torch.zeros(1,15,3),_gaits=torch.zeros(1),_perturb_cfg={'loco_failure_penalty':100.})
        phase=torch.tensor([[1.,0.]]).repeat(n,1)
        ctx=types.SimpleNamespace(a=agent,e=env,mean=torch.zeros(146),std=torch.ones(146),low=-torch.ones(34),high=torch.ones(34))
        ctx.obs=lambda x,m,p:x
        ctx.clock_phase=lambda m,t:phase
        def policy(x,m,p,sample_actions=False):
            from supermimic_race import sample_normalized_action
            dist=model.eval_actor(x)
            action=sample_normalized_action(dist) if sample_actions else dist.mode
            self.assertTrue(action.requires_grad)
            return dist.mode,action.clamp(ctx.low,ctx.high),phase
        ctx.policy=policy
        ctx.head_context=lambda m,p,a,pert:torch.zeros(len(m),1)
        x=torch.zeros(n,146);x[:,1]=1;x[:,6]=1
        b=dict(x=x[None],history=x[:,None].repeat(1,3,1)[None],history_xy=torch.zeros(1,n,3,2),
               motion=torch.zeros(1,n,dtype=torch.long),phase=phase[None],pert=torch.ones(1,n,dtype=torch.bool),
               age=torch.ones(1,n)*10,times=torch.zeros(1,n))
        replay=types.SimpleNamespace(sample=lambda batch,h:b)
        class Scorer:
            def __call__(self,h,xy,m,p,age,t,pert):return 1-(1-h[:,-1,0]).square(),None
            def failure(self,x,xy,m,a,p):return torch.zeros(len(x),dtype=torch.bool),torch.zeros(len(x))
        old=model.motor.detach().clone();old_w=[p.detach().clone() for p in wm.parameters()]
        result=update(wm,replay,ctx,torch.optim.Adam([model.motor],lr=.001),
                      torch.optim.Adam(model.value.parameters(),lr=.001),Scorer(),batch=n,horizon=3)
        self.assertFalse(result['rejected']);self.assertGreater(float(model.motor.detach()),float(old))
        self.assertFalse(result['stochastic_imagination']);self.assertEqual(result['imagined_action_noise_rms'],0.)
        self.assertGreater(float(model.value.weight.detach().abs().sum()),0.)
        for p,old in zip(wm.parameters(),old_w):torch.testing.assert_close(p,old)

        # Separate bootstrap is evaluated with observation gradients, but is
        # never optimized by the online critic optimizer.
        from supermimic_target_critic import make_target
        target=make_target(model);saved_target=target.value.weight.detach().clone()
        target_calls=[]
        hook=target.value.register_forward_hook(lambda module,args,output:target_calls.append(output.requires_grad))
        targeted=update(wm,replay,ctx,torch.optim.Adam([model.motor],lr=.001),
            torch.optim.Adam(model.value.parameters(),lr=.001),Scorer(),batch=n,horizon=3,value_model=target)
        hook.remove()
        self.assertTrue(targeted['separate_bootstrap_critic']);self.assertEqual(target_calls,[True])
        torch.testing.assert_close(target.value.weight,saved_target)
        self.assertFalse(torch.equal(model.value.weight,target.value.weight))
        self.assertIsNone(target.value.weight.grad)

        class ReciprocalScorer(Scorer):
            def __call__(self,h,xy,m,p,age,t,pert):
                costs=(1-h[:,-1,:1]).square()
                return (1+costs.sum(-1)).reciprocal(),costs
        wm._direct_tracking_scale=.25
        old_actor=model.motor.detach().clone()
        direct=update(wm,replay,ctx,torch.optim.Adam([model.motor],lr=.001),
            torch.optim.Adam(model.value.parameters(),lr=.001),ReciprocalScorer(),batch=n,horizon=3,
            direct_tracking_gradient=True,stochastic_actor=True,critic_weight=0.)
        self.assertTrue(direct['direct_tracking_gradient'])
        self.assertEqual(direct['direct_tracking_scale'],.25)
        self.assertGreater(float(model.motor.detach()),float(old_actor))
        self.assertTrue(all(p.requires_grad for p in wm.parameters()))
        self.assertTrue(all(p.grad is None for p in wm.parameters()))
        # Critic-free mode must not evaluate/update it, including at timeouts.
        old_actor=model.motor.detach().clone();old_value=model.value.weight.detach().clone()
        def forbidden(obs):raise AssertionError('Critic-free path evaluated critic')
        model.eval_critic=forbidden;b['age'].fill_(118.)
        no_critic=update(wm,replay,ctx,torch.optim.Adam([model.motor],lr=.001),
                        torch.optim.Adam(model.value.parameters(),lr=.001),Scorer(),batch=n,horizon=3,critic_weight=0.)
        self.assertFalse(no_critic['critic_enabled']);self.assertEqual(no_critic['critic_loss'],0.)
        self.assertGreater(float(model.motor.detach()),float(old_actor))
        torch.testing.assert_close(model.value.weight,old_value,rtol=0,atol=0)
        # The actual imagined update must pass the matching current/next clock
        # to both trajectory values and every shuffled critic minibatch.
        from supermimic_value_context import install,parameters,features,evaluate
        model.eval_critic=lambda obs:model.value(obs)
        install(model)
        env._mse_only=False;env._perturb_cfg.update(ae_ticks=30,blend_ticks=30)
        b['age'][0]=torch.tensor([28.,59.,118.,10.])
        b['x'][0,:,0]=torch.tensor([.1,.2,.3,.4])
        observed=[]
        def capture(m,o,c):
            observed.append((o.detach().clone(),c.detach().clone()))
            return evaluate(m,o,c)
        with patch('supermimic_value_context.evaluate',side_effect=capture):
            contextual=update(wm,replay,ctx,torch.optim.Adam([model.motor],lr=.001),
                torch.optim.Adam(parameters(model),lr=.001),Scorer(),batch=n,horizon=3)
        self.assertTrue(contextual['critic_task_context'])
        self.assertGreater(contextual['critic_context_weight_l2'],0.)
        age=b['age'][0][None]+torch.arange(4.)[:,None]
        expected=features(env,age,torch.ones_like(age,dtype=torch.bool)).flatten(0,1)
        torch.testing.assert_close(observed[0][1],expected)
        all_obs,all_context=observed[0]
        # Only pre-transition observations may be used as critic-fit inputs.
        all_obs=all_obs[:-n];all_context=all_context[:-n]
        self.assertEqual(len(observed),21)
        for obs,context in observed[1:]:
            matches=(obs[:,None]==all_obs[None]).all(-1)
            self.assertTrue(bool(matches.any(-1).all()))
            torch.testing.assert_close(context,all_context[matches.long().argmax(-1)])
        # Exercise the actual full-imagination path, not the older model updater.
        old_actor=model.motor.detach().clone();old_w=[p.detach().clone() for p in wm.parameters()]
        stochastic=update(wm,replay,ctx,torch.optim.Adam([model.motor],lr=.001),
            torch.optim.Adam(parameters(model),lr=.001),Scorer(),batch=n,horizon=3,
            stochastic_actor=True,critic_weight=0.,stop_phase_gradient=True)
        self.assertTrue(stochastic['stochastic_imagination']);self.assertFalse(stochastic['rejected'])
        self.assertTrue(stochastic['stop_phase_gradient'])
        self.assertGreater(stochastic['imagined_action_noise_rms'],.05)
        self.assertLess(stochastic['imagined_action_noise_rms'],.1)
        self.assertGreater(float(model.motor.detach()),float(old_actor))
        for p,old in zip(wm.parameters(),old_w):torch.testing.assert_close(p,old)


if __name__=='__main__':unittest.main()
