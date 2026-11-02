"""Exercise the pinned library implementation and our phase-compatible hook."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace, ModuleType
import torch

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = str(ROOT/'Saved/MimicKitSuperMimic/dataset/source.zip')
sys.path[:0] = [ARCHIVE+'/MimicKit/mimickit', ARCHIVE+'/pipeline']
# These CPU checks never render or log videos. Avoid loading MoviePy merely
# through BaseAgent's logger imports; algorithm modules remain the real library.
sys.modules['util.video']=ModuleType('util.video')
from learning.ppo_agent import PPOAgent
from learning.experience_buffer import ExperienceBuffer
from envs.base_env import DoneFlags
from util import mp_util
from supermimic_awr import install, merged_rollouts
from learning.awr_agent import AWRAgent


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.mean = torch.nn.Parameter(torch.zeros(1))
        self.phase = torch.nn.Parameter(torch.zeros(2))

    def eval_critic(self, obs):
        return obs[..., :1]

    def eval_actor(self, obs):
        return torch.distributions.Independent(torch.distributions.Normal(
            self.mean.expand(len(obs), 1), torch.ones(len(obs), 1)), 1)

    def eval_phase(self, obs):
        return self.phase.expand(len(obs), 2)


def agent():
    model = Model()
    a = SimpleNamespace(_model=model, _obs_norm=SimpleNamespace(normalize=lambda x:x),
        _a_norm=SimpleNamespace(normalize=lambda x:x), _exp_buffer=ExperienceBuffer(3, 2, 'cpu'),
        _critic_eval_batch_size=0, _discount=.99, _td_lambda=.98, _norm_adv_clip=4.,
        _awr_temp=1., _a_weight_clip=20., _phase_weight=.2,
        _action_bound_weight=0., _action_entropy_weight=0., _action_reg_weight=0.,
        _actor_optimizer=SimpleNamespace(_optimizer=torch.optim.Adam(model.parameters(),lr=1.125e-6)),
        eval=lambda:None, _compute_succ_val=lambda:0., _compute_fail_val=lambda:0.)
    a._build_train_data=lambda:PPOAgent._build_train_data(a)
    return a


class CompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mp_util.init(0, 1, 'cpu', 6800)

    def test_failure_does_not_bootstrap_but_timeout_does(self):
        a=agent();b=a._exp_buffer
        b.set_data('obs',torch.full((3,2,1),5.))
        b.set_data('next_obs',torch.full((3,2,1),10.))
        b.set_data('reward',torch.tensor([[1.,1.],[-100.,1.],[500.,500.]]))
        b.set_data('done',torch.tensor([[DoneFlags.NULL.value]*2,
            [DoneFlags.FAIL.value,DoneFlags.TIME.value],[DoneFlags.NULL.value]*2]))
        b.set_data('rand_action_mask',torch.ones(3,2))
        before=[p.clone() for p in a._model.parameters()]
        install(a);a._build_train_data()
        target=b.get_data('tar_val')
        self.assertAlmostEqual(float(target[1,0]),-100.,places=5)
        self.assertAlmostEqual(float(target[1,1]),10.9,places=5)
        self.assertEqual(a._awr_audit['critic_target_max_error'],0.)
        self.assertTrue(all(torch.equal(x,y) for x,y in zip(before,a._model.parameters())))

    def test_weighted_real_action_and_phase_mask(self):
        a=agent();install(a)
        batch=dict(obs=torch.ones(2,1),action=torch.tensor([[1.],[-1.]]),
            a_weight=torch.tensor([20.,.05]),rand_action_mask=torch.ones(2),
            next_phase=torch.tensor([[1.,0.],[0.,100.]]),phase_supervision=torch.tensor([1.,0.]))
        loss=a._compute_actor_loss(batch)['actor_loss'];loss.backward()
        self.assertLess(float(a._model.mean.grad),0.)
        self.assertLess(float(a._model.phase.grad[0]),0.)
        self.assertEqual(float(a._model.phase.grad[1]),0.)

    def test_replay_keeps_returns_separate_and_samples_all_segments(self):
        a=agent();parts=[];targets=[]
        for reward in [1.,100.]:
            b=ExperienceBuffer(3,2,'cpu');a._exp_buffer=b
            b.set_data('obs',torch.full((3,2,1),5.))
            b.set_data('next_obs',torch.full((3,2,1),10.))
            b.set_data('reward',torch.full((3,2),reward))
            b.set_data('done',torch.full((3,2),DoneFlags.NULL.value))
            b.set_data('rand_action_mask',torch.ones(3,2))
            parts.append({k:v.clone() for k,v in b._buffers.items()})
            AWRAgent._build_train_data(a)
            targets.append(b.get_data('tar_val').clone())
        merged=merged_rollouts(parts,'cpu');a._exp_buffer=merged
        AWRAgent._build_train_data(a)
        torch.testing.assert_close(merged.get_data('tar_val'),torch.cat(targets,1))
        values=merged.sample(12)['reward']
        self.assertEqual(int((values==1.).sum()),6)
        self.assertEqual(int((values==100.).sum()),6)

    def test_replay_restore_and_update_budget(self):
        a=agent();b=a._exp_buffer
        for key,data in dict(obs=torch.full((3,2,1),5.),next_obs=torch.full((3,2,1),10.),
            reward=torch.tensor([[1.,2.],[-100.,1.],[3.,4.]]),
            done=torch.tensor([[0,0],[DoneFlags.FAIL.value,0],[0,0]]),
            rand_action_mask=torch.ones(3,2)).items():b.set_data(key,data)
        b._total_samples=6
        a.train=lambda:None;a.get_num_envs=lambda:2
        a._critic_batch_size=a._actor_batch_size=1
        a._critic_epochs=2;a._actor_epochs=5
        calls=[]
        a._update_critic=lambda batch,steps:calls.append(('critic',batch,steps)) or {}
        a._update_actor=lambda batch,steps:calls.append(('actor',batch,steps)) or {}
        install(a,replay_rollouts=4)
        for _ in range(5):
            a._build_train_data();a._update_model()
            self.assertIs(a._exp_buffer,b)
        self.assertEqual(a._awr_audit['replay_rollouts'],4)
        self.assertEqual(a._awr_audit['replay_samples'],24)
        self.assertEqual(calls[-2:],[('critic',2,6),('actor',2,15)])
        self.assertEqual(a._awr_audit['refreshed_after_critic'],1.)


if __name__=='__main__':unittest.main()
