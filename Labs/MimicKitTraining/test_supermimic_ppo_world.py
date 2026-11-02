"""Check the imagined/native-PPO boundary, using the pinned real PPO targets."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace, ModuleType
import torch

ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=str(ROOT/'Saved/MimicKitSuperMimic/dataset/source.zip')
sys.path[:0]=[ARCHIVE+'/MimicKit/mimickit',ARCHIVE+'/pipeline']
sys.modules['util.video']=ModuleType('util.video')
from learning.ppo_agent import PPOAgent
from envs.base_env import DoneFlags
from util import mp_util
from supermimic_ppo_world import imagined_rollout,done_and_reward


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__();self.weight=torch.nn.Parameter(torch.tensor(.2))
    def eval_actor(self,obs):
        return torch.distributions.Independent(torch.distributions.Normal(
            self.weight.expand(len(obs),2),torch.full((len(obs),2),.075)),1)
    def eval_phase(self,obs):return torch.tensor([3.,4.]).expand(len(obs),2)
    def eval_critic(self,obs):return torch.full((*obs.shape[:-1],1),10.)


class World:
    def step(self,x,action):
        result=x.clone();result[:,0]+=1;return result
    def terminal(self,x):return torch.full((len(x),1),-100.)


class Scorer:
    def __call__(self,h,xy,m,p,age,times,pert):return torch.ones(len(m)),None
    def failure(self,x,xy,m,age,pert):return pert&(age>=2),torch.zeros(len(m))


class Replay:
    def sample(self,batch,length):
        assert batch==2 and length==1
        x=torch.zeros(2,146);x[:,1]=1.;x[:,6]=1.
        return {k:v[None].clone() for k,v in dict(x=x,history=x[:,None].repeat(1,3,1),
            history_xy=torch.zeros(2,3,2),motion=torch.tensor([0,1]),
            phase=torch.tensor([[1.,0.],[1.,0.]]),age=torch.tensor([0.,298.]),
            times=torch.tensor([0.,298/30.]),pert=torch.tensor([True,False])).items()}


def context():
    identity=SimpleNamespace(normalize=lambda x:x,unnormalize=lambda x:x)
    a=SimpleNamespace(_model=Model(),_obs_norm=identity,_a_norm=identity,
        _critic_eval_batch_size=0,_discount=.99,_td_lambda=.98,_norm_adv_clip=4.,
        eval=lambda:None,_compute_succ_val=lambda:0.,_compute_fail_val=lambda:0.)
    e=SimpleNamespace(_body_com=torch.zeros(1,1,3),_gaits=torch.tensor([0.,0.]),
        _perturb_cfg={'loco_failure_penalty':100.})
    ctx=SimpleNamespace(a=a,e=e,mean=torch.zeros(154),std=torch.ones(154),device='cpu',
        low=torch.tensor([-1.,-1.]),high=torch.tensor([1.,1.]),
        commands=lambda m,p:torch.cat((torch.zeros(len(m),6),p),-1),
        clock_phase=lambda m,t:torch.tensor([0.,1.]).expand(len(m),2),
        head_context=lambda m,p,a,b:torch.zeros(len(m),1))
    return ctx


class RolloutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):mp_util.init(0,1,'cpu',6801)

    def test_terminal_transitions_and_resets_use_native_targets(self):
        ctx=context();before=[p.detach().clone() for p in ctx.a._model.parameters()]
        exp,metrics=imagined_rollout(World(),Replay(),ctx,Scorer(),horizon=3,batch=2)
        self.assertEqual(exp.get_sample_count(),6)
        self.assertEqual(metrics['imagined_failures'],1)
        self.assertEqual(metrics['imagined_timeouts'],1)
        torch.testing.assert_close(exp.get_data('obs')[:,0,0],torch.tensor([0.,1.,0.]))
        torch.testing.assert_close(exp.get_data('next_obs')[:,0,0],torch.tensor([1.,2.,1.]))
        self.assertEqual(int(exp.get_data('done')[1,0]),DoneFlags.FAIL.value)
        self.assertEqual(int(exp.get_data('done')[1,1]),DoneFlags.TIME.value)
        ctx.a._exp_buffer=exp;PPOAgent._build_train_data(ctx.a)
        self.assertAlmostEqual(float(exp.get_data('tar_val')[1,0]),-99.,places=5)
        self.assertAlmostEqual(float(exp.get_data('tar_val')[1,1]),10.9,places=5)
        self.assertTrue(all(not x.requires_grad for x in exp._buffers.values()))
        self.assertTrue(all(torch.equal(p,q) for p,q in zip(ctx.a._model.parameters(),before)))

    def test_phase_feedback_and_supervision_remain_separate(self):
        ctx=context();exp,_=imagined_rollout(World(),Replay(),ctx,Scorer(),horizon=3,batch=2)
        torch.testing.assert_close(exp.get_data('next_obs')[0,0,-2:],torch.tensor([.6,.8]))
        torch.testing.assert_close(exp.get_data('next_obs')[0,1,-2:],torch.tensor([0.,1.]))
        torch.testing.assert_close(exp.get_data('next_phase')[0],torch.tensor([[0.,1.],[0.,1.]]))
        torch.testing.assert_close(exp.get_data('phase_supervision')[0],torch.tensor([0.,1.]))
        dist=ctx.a._model.eval_actor(exp.get_data('obs')[0])
        torch.testing.assert_close(exp.get_data('a_logp')[0],dist.log_prob(exp.get_data('action')[0]))

    def test_failure_precedence_and_penalty_scope(self):
        done,reward=done_and_reward(torch.ones(3),torch.tensor([True,False,True]),
            torch.tensor([True,True,False]),torch.tensor([100.,100.,0.]))
        self.assertEqual(done.tolist(),[DoneFlags.FAIL.value,DoneFlags.TIME.value,DoneFlags.FAIL.value])
        self.assertEqual(reward.tolist(),[-99.,1.,1.])

    def test_short_branch_bootstraps_before_replay_reset(self):
        class SafeScorer(Scorer):
            def failure(self,x,xy,m,age,pert):return torch.zeros(len(m),dtype=torch.bool),torch.zeros(len(m))
        ctx=context();exp,metrics=imagined_rollout(World(),Replay(),ctx,SafeScorer(),horizon=4,batch=2,branch_horizon=2)
        torch.testing.assert_close(exp.get_data('obs')[:,0,0],torch.tensor([0.,1.,0.,1.]))
        torch.testing.assert_close(exp.get_data('next_obs')[:,0,0],torch.tensor([1.,2.,1.,2.]))
        self.assertEqual(exp.get_data('done')[:,0].tolist(),[DoneFlags.NULL.value,DoneFlags.TIME.value]*2)
        self.assertEqual(metrics['imagined_failures'],0);self.assertEqual(metrics['imagined_branch_cuts'],2)
        self.assertEqual(metrics['branch_horizon'],2)
        ctx.a._exp_buffer=exp;PPOAgent._build_train_data(ctx.a)
        self.assertAlmostEqual(float(exp.get_data('tar_val')[1,0]),10.9,places=5)
        self.assertAlmostEqual(float(exp.get_data('tar_val')[3,0]),10.9,places=5)
        # The boundary return excludes the independently sampled next segment.
        self.assertAlmostEqual(float(exp.get_data('tar_val')[0,0]),1+.99*(.02*10+.98*10.9),places=5)


if __name__=='__main__':unittest.main()
