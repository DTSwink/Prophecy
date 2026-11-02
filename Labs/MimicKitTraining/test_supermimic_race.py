"""Numerical checks for the isolated model-based experiment, CPU only."""
import unittest
import types,copy
import torch
from supermimic_race import Replay,lambda_targets,LearnedWorld,sample_normalized_action

class RaceTests(unittest.TestCase):
    def test_live_monitor_preserves_new_progress_and_failure_messages(self):
        from supermimic_kaggle import live_log_tail
        events=[dict(time=1,data='WORKERS_ALIVE'),dict(time=2,data='NEW_UNLISTED_STAGE result ready'),
                dict(time=3,data='OBJECTIVE_AUDIT_CHECK finite'),dict(time=4,data='   '),
                dict(time=5,data='new failure detail')]
        tail=live_log_tail(events,3)
        self.assertEqual(len(tail),3)
        self.assertIn('NEW_UNLISTED_STAGE',tail[0])
        self.assertIn('OBJECTIVE_AUDIT_CHECK',tail[1])
        self.assertIn('new failure detail',tail[2])

    def test_objective_directions_distinguish_conflicting_failure_and_value_gradients(self):
        from supermimic_objective_audit import component_directions
        delta=torch.zeros(2,2,dtype=torch.float64,requires_grad=True)
        dense=2*delta[:,0]+delta[:,1].square()
        value=3*delta[:,1]
        failure=-5*delta[:,0]
        gradients,directions=component_directions(dict(dense=dense,dense_critic=dense+value,
                                                        full=dense+value+failure),delta)
        torch.testing.assert_close(gradients['dense'],torch.tensor([[2.,0.],[2.,0.]],dtype=torch.float64))
        torch.testing.assert_close(gradients['full'],torch.tensor([[-3.,3.],[-3.,3.]],dtype=torch.float64))
        for direction in directions.values():
            torch.testing.assert_close(direction.square().mean(-1),torch.ones(2,dtype=torch.float64))
        self.assertTrue(bool((directions['full'][:,0]<0).all()))

    def test_directional_supervision_matches_finite_difference_and_trains_parameters(self):
        from supermimic_derivatives import directional_prediction,directional_loss
        class World(torch.nn.Module):
            def __init__(self):
                super().__init__();self.mean=torch.zeros(2);self.weight=torch.nn.Parameter(torch.tensor(.4,dtype=torch.float64))
            def step(self,x,a):return torch.stack((x[:,0]+self.weight*a[:,0].square(),x[:,1]*a[:,0]),-1)
        wm=World();u=torch.tensor([[.3,.5,.7],[.1,-.2,.4]],dtype=torch.float64)
        du=torch.tensor([[.02,-.01,.03],[-.03,.05,.02]],dtype=torch.float64)
        actual=directional_prediction(wm,u,du)
        eps=1e-5
        measured=(wm.step((u+eps*du)[:,:2],(u+eps*du)[:,2:])-wm.step((u-eps*du)[:,:2],(u-eps*du)[:,2:]))/(2*eps)
        torch.testing.assert_close(actual,measured,rtol=1e-7,atol=1e-10)
        target=torch.stack((du[:,0]+2*u[:,2]*du[:,2],du[:,1]*u[:,2]+u[:,1]*du[:,2]),-1)
        loss=directional_loss(wm,dict(direction_u=u,direction_du=du,direction_dy=target))
        loss.backward();self.assertLess(float(wm.weight.grad),0.)
        self.assertTrue(torch.isfinite(wm.weight.grad))

    def test_direction_pairs_are_nearest_and_do_not_leak_heldout_worlds(self):
        from supermimic_derivatives import nearest_pairs,prepare_pairs
        u=torch.tensor([[0.,0.],[1.,0.],[3.,0.]])
        pairs,source,target=nearest_pairs(u,2*u,torch.ones(2),neighbors=1)
        self.assertEqual(target.tolist(),[1,0,1])
        torch.testing.assert_close(pairs['direction_dy'],2*pairs['direction_du'])
        b=Replay(20,'cpu',16);torch.manual_seed(1)
        for _ in range(12):b.add(x=torch.randn(20,2),a=torch.randn(20,1),next_x=torch.randn(20,2))
        pools,stats=prepare_pairs(b,100,20)
        for name,p in pools.items():
            for k in ['source_index','target_index']:
                self.assertTrue(bool(((p[k]%20%10==0)==(name=='heldout')).all()))
        self.assertEqual(stats['train']['pairs'],500)

    def test_rotation_integration_matches_matrix_exponential_and_zero_gradient(self):
        from supermimic_structured import rotation_increment
        v=torch.tensor([[0.,0.,0.],[.3,-.4,.7]],requires_grad=True)
        x,y,z=v.unbind(-1);zero=torch.zeros_like(x)
        skew=torch.stack((zero,-z,y,z,zero,-x,-y,x,zero),-1).reshape(-1,3,3)
        torch.testing.assert_close(rotation_increment(v),torch.matrix_exp(skew),atol=2e-6,rtol=2e-6)
        rotation_increment(v)[:,0,1].sum().backward()
        self.assertTrue(bool(torch.isfinite(v.grad).all()))
        torch.testing.assert_close(v.grad[0],torch.tensor([0.,0.,-1.]))

    def test_integrated_prior_preserves_com_path_and_rotates_local_joints(self):
        from supermimic_structured import integrate_observation,matrix_from_six,rotation_increment
        raw=torch.zeros(1,146);raw[:,0]=1.
        raw[:,1:7]=torch.tensor([1.,0.,0.,0.,0.,1.])
        raw[:,13:97]=raw[:,1:7].repeat(1,14)
        raw[:,9]=2.;raw[:,10]=3.;raw[:,97]=6.
        mapping=torch.zeros(34,42);mapping[0,2]=1.
        com=torch.tensor([0.,.2,.1]);delta=torch.zeros_like(raw,requires_grad=True)
        predicted=integrate_observation(raw,delta,mapping,com)
        root=matrix_from_six(predicted[:,1:7]);child=matrix_from_six(predicted[:,13:19])
        torch.testing.assert_close(root,rotation_increment(torch.tensor([[.1,0.,0.]])))
        torch.testing.assert_close(child,rotation_increment(torch.tensor([[0.,0.,.2]])))
        new_com_height=predicted[:,0]+(root@com[:,None]).squeeze(-1)[:,2]
        torch.testing.assert_close(new_com_height,torch.tensor([1.+.1+2./30]))
        predicted.square().sum().backward()
        self.assertTrue(bool(torch.isfinite(delta.grad).all()))
        stationary=raw.clone();stationary[:,7:13]=0;stationary[:,97:131]=0
        torch.testing.assert_close(integrate_observation(stationary,torch.zeros_like(raw),mapping,com),stationary)

    def test_constant_reference_rotation_has_zero_finite_phase_gradient(self):
        from supermimic_exact_reward import safe_reference_slerp
        q0=torch.tensor([[0.,0.,0.,1.],[0.,0.,0.,1.]])
        angle=torch.tensor(.7)
        q1=torch.stack((q0[0],torch.stack((angle*0,angle*0,angle.sin(),angle.cos()))))
        t=torch.tensor([.37,.37],requires_grad=True)
        output=safe_reference_slerp(q0,q1,t)
        torch.testing.assert_close(output[0],q0[0])
        torch.testing.assert_close(output[1,2:],torch.stack(((angle*t[1]).sin(),(angle*t[1]).cos())))
        output.sum().backward();self.assertTrue(bool(torch.isfinite(t.grad).all()));self.assertEqual(float(t.grad[0]),0.)

    def test_exact_reward_kinematics_have_correct_origin_velocity_and_gradient(self):
        from supermimic_exact_reward import forward_kinematics,world_velocities
        skeleton=types.SimpleNamespace(parents=[-1,0,1],
            translations=torch.tensor([[0.,0.,0.],[1.,0.,0.],[1.,0.,0.]]),
            local_matrices=torch.eye(3).expand(3,-1,-1))
        root=torch.tensor([[2.,3.,4.]],requires_grad=True)
        pos,rot=forward_kinematics(skeleton,root,torch.eye(3)[None],torch.eye(3).expand(1,2,3,3))
        torch.testing.assert_close(pos,torch.tensor([[[2.,3.,4.],[3.,3.,4.],[4.,3.,4.]]]))
        v,w=world_velocities(pos,rot,torch.tensor([[1.,0.,0.]]),torch.tensor([[0.,0.,2.]]),
            torch.tensor([[[0.,0.,1.],[0.,0.,0.]]]),skeleton.parents)
        torch.testing.assert_close(v,torch.tensor([[[1.,0.,0.],[1.,2.,0.],[1.,5.,0.]]]))
        torch.testing.assert_close(w,torch.tensor([[[0.,0.,2.],[0.,0.,3.],[0.,0.,3.]]]))
        pos.sum().backward();torch.testing.assert_close(root.grad,torch.full_like(root,3.))

    def test_decoupled_update_uses_real_states_and_changes_actor(self):
        from supermimic_decoupled import update
        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__();self.actor=torch.nn.Linear(2,2)
                torch.nn.init.zeros_(self.actor.weight);torch.nn.init.constant_(self.actor.bias,.1)
            def get_actor_params(self):return list(self.actor.parameters())
            def eval_actor(self,x):
                mean=self.actor(x);return types.SimpleNamespace(mode=mean,stddev=torch.full_like(mean,.075))
            def eval_critic(self,x):return x.sum(-1,keepdim=True)
        class World(torch.nn.Module):
            def step(self,x,a):return x+2*a+5  # Deliberately wrong forward prediction.
            def heads(self,h,c):return h[:,-1].sum(-1),torch.full((len(h),),-5.)
        m=Model();target=copy.deepcopy(m)
        ctx=types.SimpleNamespace(a=types.SimpleNamespace(_model=m,_phase_weight=0.,_action_bound_weight=0.),
            e=types.SimpleNamespace(_gaits=torch.ones(1),_perturb_cfg={'loco_failure_penalty':100.}),
            low=-torch.ones(2),high=torch.ones(2),obs=lambda x,m,p:x,
            clock_phase=lambda m,t:torch.zeros(len(m),2),head_context=lambda *args:None)
        ctx.policy=lambda x,motion,phase:(m.actor(x),m.actor(x),torch.zeros(len(x),2))
        b=Replay(20,'cpu',16);x=torch.full((20,2),.2)
        for t in range(4):
            raw=m.actor(x).detach();nxt=x+2*raw
            b.add(x=x,next_x=nxt,a=raw,raw_a=raw,mean_a=raw,history=x[:,None].expand(-1,3,-1),
                  motion=torch.zeros(20,dtype=torch.long),phase=torch.zeros(20,2),next_phase=torch.zeros(20,2),
                  times=torch.full((20,),t/30),age=torch.full((20,),t),pert=torch.ones(20,dtype=torch.bool),
                  base_reward=nxt.sum(-1),done=torch.zeros(20,dtype=torch.bool),fail=torch.zeros(20,dtype=torch.bool))
            x=nxt
        before=m.actor.bias.detach().clone()
        result=update(World(),b,ctx,torch.optim.Adam(m.parameters(),lr=1e-4),target,4,batch=8)
        self.assertEqual(result['real_forward_max_error'],0)
        self.assertLess(result['on_policy_mean_max_error'],1e-6)
        self.assertFalse(result['rejected']);self.assertGreater(result['actor_grad_norm'],0)
        self.assertTrue(bool((m.actor.bias.detach()>before).all()))

    def test_decoupled_forward_is_exact_but_derivative_uses_model(self):
        from supermimic_decoupled import anchor,recent_batch
        action=torch.tensor([.2,.7],requires_grad=True)
        real=torch.tensor([10.,-4.],requires_grad=True)
        state=anchor(action.square(),real)
        torch.testing.assert_close(state,real,rtol=0,atol=0)
        state.square().sum().backward()
        torch.testing.assert_close(action.grad,4*real.detach()*action.detach())
        self.assertIsNone(real.grad)
        b=Replay(20,'cpu',capacity=16)
        for i in range(35):b.add(t=torch.full((20,),i),world=torch.arange(20))
        last=recent_batch(b,8,4)
        torch.testing.assert_close(last['t'],torch.arange(31,35)[:,None].expand(4,8))
        self.assertTrue(bool((last['world']%10!=0).all()))
        fresh=recent_batch(b,100,4,fresh_ticks=8)
        self.assertEqual(fresh['t'].shape,(4,90))
        self.assertTrue(bool((fresh['t'][1:]-fresh['t'][:-1]==1).all()))
        self.assertTrue(bool(((fresh['t']>=27)&(fresh['t']<=34)).all()))
        self.assertEqual(len(set(zip(fresh['t'][0].tolist(),fresh['world'][0].tolist()))),90)
        self.assertTrue(bool((fresh['world']%10!=0).all()))

    def test_failure_surrogate_tracks_original_speed_and_direction(self):
        from supermimic_exact_reward import com2_failure_surrogate
        v=torch.tensor([[1.,0.],[.69,0.],[1.71,0.],[.7,.72],[.72,.7],[0.,0.]],requires_grad=True)
        target=torch.tensor([[1.,0.]]).expand_as(v)
        hard,soft=com2_failure_surrogate(v,target)
        self.assertEqual(hard.tolist(),[False,True,True,True,False,True])
        soft.sum().backward();self.assertTrue(bool(torch.isfinite(v.grad).all()))
        self.assertLess(float(v.grad[1,0]),0.)
        self.assertGreater(float(v.grad[2,0]),0.)
        self.assertLess(float(v.grad[3,0]),0.)
        self.assertGreater(float(v.grad[3,1]),0.)

    def test_noise_is_reparameterized_and_independent_of_reset_rng(self):
        mean=torch.zeros(10000,2,requires_grad=True)
        dist=types.SimpleNamespace(mode=mean,stddev=torch.full_like(mean,.075))
        a=sample_normalized_action(dist,torch.Generator().manual_seed(75))
        torch.randn(1234)
        b=sample_normalized_action(dist,torch.Generator().manual_seed(75))
        torch.testing.assert_close(a,b)
        self.assertAlmostEqual(float(a.std().detach()),.075,delta=.002)
        a.sum().backward();torch.testing.assert_close(mean.grad,torch.ones_like(mean))

    def test_real_critic_learns_terminal_cost_without_future_value(self):
        from supermimic_pilot import fit_real_critic
        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__();self.value=torch.nn.Linear(2,1)
                torch.nn.init.zeros_(self.value.weight);torch.nn.init.zeros_(self.value.bias)
            def eval_critic(self,x):return self.value(x)
            def get_critic_params(self):return list(self.value.parameters())
        m=Model();target=copy.deepcopy(m)
        with torch.no_grad():target.value.bias.fill_(100.)
        for p in target.parameters():p.requires_grad_(False)
        ctx=types.SimpleNamespace(a=types.SimpleNamespace(_model=m),
            e=types.SimpleNamespace(_gaits=torch.ones(1),_perturb_cfg={'loco_failure_penalty':100.}),
            obs=lambda x,motion,phase:x)
        b=Replay(20,'cpu',16)
        for _ in range(12):
            b.add(x=torch.zeros(20,2),next_x=torch.zeros(20,2),motion=torch.zeros(20,dtype=torch.long),
                  phase=torch.zeros(20,2),next_phase=torch.zeros(20,2),base_reward=torch.ones(20),
                  fail=torch.ones(20,dtype=torch.bool),done=torch.ones(20,dtype=torch.bool),
                  pert=torch.ones(20,dtype=torch.bool))
        loss=fit_real_critic(ctx,b,torch.optim.Adam(m.parameters(),lr=.01),target)
        self.assertTrue(loss>0);self.assertLess(float(m.value.bias.detach()),-.15)
        # The copied bootstrap critic follows slowly and receives no gradients.
        self.assertTrue(all(p.grad is None for p in target.parameters()))
        self.assertAlmostEqual(float(target.value.bias),100*.995+float(m.value.bias.detach())*.005,places=4)

    def test_failure_does_not_bootstrap_or_leak_next_episode(self):
        r=torch.tensor([[1.],[-99.],[500.]])
        c=torch.tensor([[1.],[0.],[1.]])
        values=torch.full((4,1),1000.)
        targets=lambda_targets(r,c,torch.zeros_like(r),values,gamma=.99,lam=1.)
        self.assertAlmostEqual(float(targets[1]),-99.)
        self.assertAlmostEqual(float(targets[0]),1-.99*99,places=4)

    def test_timeout_uses_final_state_value(self):
        r=torch.ones(1,1);c=torch.zeros_like(r);v=torch.tensor([[2.],[7.]])
        target=lambda_targets(r,c,torch.tensor([[7.]]),v)
        self.assertAlmostEqual(float(target),1+.99*7,places=5)

    def test_ring_windows_and_holdout_worlds(self):
        b=Replay(20,'cpu',capacity=16)
        for t in range(35):b.add(t=torch.full((20,),t),world=torch.arange(20))
        for held in [False,True]:
            s=b.sample(512,8,holdout=held)
            self.assertTrue(torch.all(s['t'][1:]-s['t'][:-1]==1))
            self.assertTrue(torch.all(s['t']>=19))
            self.assertTrue(torch.all((s['world']%10==0)==held))

    def test_value_gradient_weights_and_model_objective(self):
        from supermimic_model_audit import value_gradient_weights
        from supermimic_race import model_loss
        g=torch.tensor([[2.,0.],[2.,0.],[1000.,0.]])
        weights,stats=value_gradient_weights(g,torch.tensor([True,True,False]))
        torch.testing.assert_close(weights,torch.tensor([[2.,0.],[2.,0.],[2.,0.]]))
        self.assertEqual(stats['norm_clip_95'],2.)
        class World(torch.nn.Module):
            def __init__(self):
                super().__init__();self.delta=torch.nn.Parameter(torch.zeros(2));self.value_weighted=False
            def step(self,x,a):return x+self.delta
            def heads(self,h,c):return torch.zeros(len(h)),torch.zeros(len(h))
        world=World();ctx=types.SimpleNamespace(head_context=lambda *args:None)
        batch=dict(x=torch.zeros(1,3,2),next_x=torch.ones(1,3,2),a=torch.zeros(1,3,1),
            history=torch.zeros(1,3,3,2),motion=torch.zeros(1,3,dtype=torch.long),next_phase=torch.zeros(1,3,2),
            age=torch.zeros(1,3),pert=torch.zeros(1,3,dtype=torch.bool),base_reward=torch.zeros(1,3),
            fail=torch.zeros(1,3,dtype=torch.bool),done=torch.zeros(1,3,dtype=torch.bool),value_weights=weights[None])
        loss,metrics=model_loss(world,batch,ctx);loss.backward()
        torch.testing.assert_close(world.delta.grad,torch.tensor([-1.,-1.]))
        world.zero_grad();world.value_weighted=True
        loss,weighted_metrics=model_loss(world,batch,ctx);loss.backward()
        torch.testing.assert_close(world.delta.grad,torch.tensor([-2.,0.]))
        torch.testing.assert_close(metrics['state_nse'],weighted_metrics['state_nse'])
        world.zero_grad();world.value_add_mse=True
        loss,_=model_loss(world,batch,ctx);loss.backward()
        torch.testing.assert_close(world.delta.grad,torch.tensor([-3.,-1.]))

    def test_reachable_value_gradient_discards_constants_and_folds_dependencies(self):
        from supermimic_model_audit import reachable_value_gradient
        def skeleton(raw):return torch.stack((raw[:,0],torch.zeros_like(raw[:,0]),2*raw[:,0]),-1)
        wm=types.SimpleNamespace(mean=torch.zeros(3),std=torch.tensor([2.,3.,4.]),skeleton=skeleton)
        model=types.SimpleNamespace(eval_critic=lambda x:(x*torch.tensor([3.,1e6,5.])).sum(-1))
        ctx=types.SimpleNamespace(a=types.SimpleNamespace(_model=model),obs=lambda x,m,p:x)
        x=torch.tensor([[.2,0.,.2]],requires_grad=True)
        g,ambient,p=reachable_value_gradient(ctx,wm,x,None,None)
        torch.testing.assert_close(ambient,torch.tensor([[3.,1e6,5.]]))
        torch.testing.assert_close(g,torch.tensor([[8.,0.,0.]]))
        torch.testing.assert_close(p,x.detach())
        direction=torch.tensor([[.01,.02,.03]])
        def value(u):return model.eval_critic((skeleton(u*wm.std)-wm.mean)/wm.std)
        measured=(value(x.detach()+direction)-value(x.detach()-direction))/2
        torch.testing.assert_close(measured,(g*direction).sum(-1))

    def test_regularized_dynamics_keeps_linear_weights_and_action_gradients(self):
        from supermimic_structured import SimNorm,regularize_dynamics
        torch.set_num_threads(1)
        x=torch.randn(4,32,requires_grad=True)
        y=SimNorm(8)(x)
        torch.testing.assert_close(y.reshape(4,4,8).sum(-1),torch.ones(4,4))
        (y*torch.randn_like(y)).sum().backward()
        self.assertTrue(bool(torch.isfinite(x.grad).all()))
        original=torch.nn.Sequential(torch.nn.Linear(5,32),torch.nn.SiLU(),
            torch.nn.Linear(32,32),torch.nn.SiLU(),torch.nn.Linear(32,3))
        linears=[m for m in original if isinstance(m,torch.nn.Linear)]
        smooth=regularize_dynamics(original)
        self.assertEqual([m for m in smooth if isinstance(m,torch.nn.Linear)],linears)
        for p in smooth.parameters():p.requires_grad_(False)
        action=torch.randn(6,5,requires_grad=True)
        smooth(action).square().sum().backward()
        self.assertTrue(bool(torch.isfinite(action.grad).all()))
        self.assertGreater(float(action.grad.abs().sum()),0.)

    def test_advantage_clip_diagnostics_separate_failure_signal(self):
        from supermimic_advantage import clipping_stats
        normalized=torch.tensor([-12.,-2.,8.,1.])
        failure=torch.tensor([True,False,False,False])
        original=normalized.clone()
        a=clipping_stats(normalized,failure,4.)
        b=clipping_stats(normalized,failure,10.)
        self.assertAlmostEqual(a['above4_fraction'],.5)
        self.assertAlmostEqual(b['above_cap_fraction'],.25)
        self.assertAlmostEqual(a['negative_mass_removed_at4'],8/14,places=6)
        self.assertAlmostEqual(b['negative_mass_removed_at_cap'],2/14,places=6)
        self.assertAlmostEqual(a['terminal_negative_mass_removed_at4'],8/12,places=6)
        torch.testing.assert_close(normalized,original)
        zero=clipping_stats(torch.ones(5),torch.zeros(5,dtype=torch.bool),4.)
        self.assertEqual(zero['negative_mass_removed_at4'],0.)
        self.assertEqual(zero['terminal_count'],0)

    def test_frozen_phase_changes_feedback_only_on_perturbed_rows(self):
        from supermimic_phase_stability import install,phase_cycles_difference
        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self._actor_layers=torch.nn.Sequential(torch.nn.Linear(4,6),torch.nn.Tanh())
                self._phase_out=torch.nn.Linear(6,2)
                self._unit_phase=True
            def eval_phase(self,obs):
                return torch.nn.functional.normalize(self._phase_out(self._actor_layers(obs)),dim=-1)
        torch.manual_seed(51)
        model=Model();obs=torch.randn(5,4);actions=torch.randn(5,2)
        env=types.SimpleNamespace(_recovery_ready=True,_recovery_ids=torch.arange(5),
            _phase_feedback_ids=torch.arange(5),_perturbed_rows=torch.tensor([1,0,1,0,1],dtype=torch.bool),
            _feedback_phase=torch.tensor([[1.,0.]]).repeat(5,1),_pending_phase=torch.zeros(5,2))
        def queue(pred):
            norm=pred.norm(dim=-1,keepdim=True)
            env._pending_phase.copy_(torch.where(norm>1e-6,pred/norm.clamp_min(1e-6),env._feedback_phase))
        env.queue_phase_prediction=queue
        def original(o,i):
            with torch.no_grad():queue(model.eval_phase(o))
            return actions,{'unchanged':True}
        agent=types.SimpleNamespace(_model=model,_env=env,_decide_action=original,
            _obs_norm=types.SimpleNamespace(normalize=lambda x:x))
        keys=list(model.state_dict());rng=torch.get_rng_state().clone()
        frozen,probe=install(agent,True)
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        a,info=agent._decide_action(obs,{})
        self.assertIs(a,actions);self.assertTrue(info['unchanged'])
        torch.testing.assert_close(env._pending_phase,model.eval_phase(obs))
        before=env._pending_phase.clone()
        with torch.no_grad():model._phase_out.bias.add_(torch.tensor([.5,-.6]))
        live=model.eval_phase(obs).detach()
        agent._decide_action(obs,{})
        torch.testing.assert_close(env._pending_phase[env._perturbed_rows],before[env._perturbed_rows])
        torch.testing.assert_close(env._pending_phase[~env._perturbed_rows],live[~env._perturbed_rows])
        self.assertEqual(list(model.state_dict()),keys)
        self.assertTrue(all(not p.requires_grad for p in frozen.parameters()))
        stats=probe();self.assertEqual(stats['predictor_parameter_delta_l2'],0.)
        self.assertEqual(stats['deployed_fixed_probe_drift_rms_cycles'],0.)
        self.assertGreater(stats['live_drift_rms_cycles'],0.)
        def angle(c):return torch.tensor([[torch.cos(torch.tensor(c*2*torch.pi)),torch.sin(torch.tensor(c*2*torch.pi))]])
        torch.testing.assert_close(phase_cycles_difference(angle(.01),angle(.99)),torch.tensor([.02]),atol=1e-6,rtol=1e-6)

    def test_model_differentiates_actions_with_frozen_weights(self):
        torch.set_num_threads(1)
        m=LearnedWorld(torch.zeros(154),torch.ones(154),5)
        torch.nn.init.normal_(m.dynamics[-1].weight,std=.01)
        for p in m.parameters():p.requires_grad_(False)
        x=torch.randn(3,146);a=torch.randn(3,34,requires_grad=True)
        y=m.step(x,a);y.square().mean().backward()
        self.assertTrue(torch.isfinite(a.grad).all());self.assertGreater(float(a.grad.abs().sum()),0)
        self.assertTrue(all(p.grad is None for p in m.parameters()))
        for rot in [y[:,1:7],y[:,13:97].reshape(-1,6)]:
            torch.testing.assert_close(rot[:,:3].norm(dim=-1),torch.ones(len(rot)))
            torch.testing.assert_close(rot[:,3:].norm(dim=-1),torch.ones(len(rot)))
            torch.testing.assert_close((rot[:,:3]*rot[:,3:]).sum(-1),torch.zeros(len(rot)),atol=1e-5,rtol=0)

if __name__=='__main__':unittest.main()
