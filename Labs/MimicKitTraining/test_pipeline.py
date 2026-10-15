import io
import json
from pathlib import Path
import tempfile
import unittest
import random
import zipfile
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import torch
from observe import Recorder, TrainingRecorder, first_episode_end
from replay import convert, geometry, WORLD_TO_VIEW
from backup import Backups
from resume import restore

class FakeEngine:
    def __init__(self):
        self.pos=torch.tensor([[[1.,2.,3.],[2.,3.,4.]]])
        self.quat=torch.tensor([[[0.,0.,0.,1.],[0.,0.,0.,1.]]])
    def get_obj_body_names(self,char):return ['pelvis','head']
    def get_timestep(self):return 1/30
    def get_body_pos(self,char):return self.pos
    def get_body_rot(self,char):return self.quat

class FakeEnv:
    _device='cpu'
    _episode_length=1.
    def __init__(self):
        self._engine=FakeEngine()
        self._done_buf=torch.zeros(1)
        self._time_buf=torch.zeros(1)
        self._reward_buf=torch.zeros(1)
    def _get_char_id(self):return 0
    def step(self,a):
        self._time_buf+=1/30
        self._engine.pos+=a
        return self._engine.pos.clone()

class FakeS3:
    def __init__(self,corrupt=False):self.data={};self.corrupt=corrupt
    def put_object(self,Bucket,Key,Body,**kwargs):self.data[Key]=Body
    def get_object(self,Bucket,Key):return {'Body':io.BytesIO(self.data[Key]+(b'broken' if self.corrupt else b''))}

class PipelineTests(unittest.TestCase):
    def test_resume_preserves_optimizer_and_global_sample_count(self):
        class Agent(torch.nn.Module):
            _device='cpu'
            def __init__(self):
                super().__init__()
                self.actor=torch.nn.Linear(2,1);self.critic=torch.nn.Linear(2,1)
                self.norm=torch.nn.Module();self.norm._mean_sq=torch.tensor([3.])
                self._actor_optimizer=SimpleNamespace(_optimizer=torch.optim.SGD(self.actor.parameters(),lr=.1,momentum=.9),_steps=7)
                self._critic_optimizer=SimpleNamespace(_optimizer=torch.optim.SGD(self.critic.parameters(),lr=.1,momentum=.9),_steps=3)
            def _init_train(self):self._sample_count=0;self._iter=0
            def _update_sample_count(self):return 32
            def step(self):
                for net,opt in [(self.actor,self._actor_optimizer),(self.critic,self._critic_optimizer)]:
                    opt._optimizer.zero_grad();net(torch.ones(1,2)).sum().backward();opt._optimizer.step()
        original=Agent();original.step()
        state=dict(completed_iteration=31,samples=4194304,
            actor_optimizer=original._actor_optimizer._optimizer.state_dict(),critic_optimizer=original._critic_optimizer._optimizer.state_dict(),
            actor_steps=7,critic_steps=3,normalizer_aux={'norm':{'_mean_sq':torch.tensor([3.]),'_new_count':0}},
            torch_rng=torch.get_rng_state(),cuda_rng=[],numpy_rng=np.random.get_state(),python_rng=random.getstate())
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/'checkpoint.zip'
            with zipfile.ZipFile(archive,'w') as z:
                for name,value in [('model.pt',original.state_dict()),('resume_state.pt',state)]:
                    b=io.BytesIO();torch.save(value,b);z.writestr(name,b.getvalue())
            resumed=Agent();report=restore(resumed,archive)
            with patch('resume.torch.cuda.is_available',return_value=False):resumed._init_train()
            self.assertEqual(resumed._sample_count,4194304)
            self.assertEqual(resumed._update_sample_count(),4194336)
            self.assertEqual(report['iteration_offset'],32)
            self.assertEqual(resumed._actor_optimizer._steps,7)
            torch.testing.assert_close(resumed.norm._mean_sq,torch.tensor([3.]))
            original.step();resumed.step()
            for a,b in zip(original.parameters(),resumed.parameters()):torch.testing.assert_close(a,b,rtol=0,atol=0)

    def test_rejects_partial_episode_and_cuts_at_first_terminal(self):
        with self.assertRaises(ValueError):first_episode_end(np.array([0,0,0]))
        self.assertEqual(first_episode_end(np.array([0,0,1,0,0,3])),3)

    def test_disabled_recorder_does_not_capture_or_change_physics(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=FakeEnv(),FakeEnv();r=Recorder(a,d)
            for _ in range(4):torch.testing.assert_close(a.step(.1),b.step(.1))
            self.assertEqual(r.count,0)

    def test_complete_recording_coordinates_and_orientation(self):
        with tempfile.TemporaryDirectory() as d:
            env=FakeEnv();r=Recorder(env,d);r.start();env.step(.1)
            env._done_buf[0]=1;env.step(.1);env._done_buf[0]=0;env.step(.1)
            meta=r.finish(4,1024)
            self.assertTrue(meta['complete_episode'])
            g=dict(names=['pelvis','head'],bones=[[0,1]],shapes=[])
            p=convert(Path(d)/'replay.npz',g,'test')
            self.assertEqual(p['rows'][0]['effective_k'],2)
            np.testing.assert_allclose(p['positions'][0][0][0],[1,3,-2])
            np.testing.assert_allclose(p['basis'][0][0][0],WORLD_TO_VIEW.T)

    def test_replay_loss_and_actual_noise_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            env=FakeEnv();r=Recorder(env,d);r.start()
            env._reward_buf[0]=-.25;env._done_buf[0]=2;env.step(.1)
            extra=dict(task='neutral_pose_mse',losses=dict(train_mse_m2=.3,test_mse_m2=.2),
                       training_action_noise_std=.005,rollout_action_noise_std=0.,worlds=256)
            r.finish(50,409600,extra_metadata=extra)
            p=convert(Path(d)/'replay.npz',dict(names=['pelvis','head'],bones=[[0,1]],shapes=[]),'test')
            self.assertEqual(p['metadata']['evaluation']['episode_mse_m2'],.25)
            self.assertEqual(p['metadata']['evaluation']['losses'],extra['losses'])
            self.assertEqual(p['metadata']['training_progress']['num_envs'],256)
            self.assertIn('training: 0.005',p['message'])
            self.assertIn('this rollout: 0.000',p['message'])
            from replay import neutral_replay_message
            self.assertIn('training: not recorded',neutral_replay_message({},.25))

    def test_training_capture_waits_for_reset_and_adds_no_steps(self):
        class Env(FakeEnv):
            _episode_length=.1
            def reset(self,ids=None):
                self._time_buf.zero_();self._done_buf.zero_();self._reward_buf.zero_()
                self._engine.pos.fill_(1.)
                return self._engine.pos.clone()
            def step(self,a):
                result=super().step(a)
                if self._time_buf[0]>=.099:self._done_buf[0]=2;self._reward_buf[0]=-.25
                return result
        with tempfile.TemporaryDirectory() as d:
            captured,plain=Env(),Env();tick=[0]
            r=TrainingRecorder(captured,d,lambda:tick[0]);captured.reset();plain.reset()
            # An output-boundary reset interrupts a partial episode. Never join
            # frames from opposite sides of that reset into a fake full episode.
            captured.step(.1);plain.step(.1);captured.reset();plain.reset()
            for _ in range(3):
                tick[0]+=1;torch.testing.assert_close(captured.step(.1),plain.step(.1))
            self.assertTrue(r.ready);self.assertFalse(r.enabled)
            meta=r.finish(3,256,dict(task='neutral_pose_mse',training_action_noise_std=.005,
                                    rollout_action_noise_std=.005))
            self.assertEqual(meta['mode'],'actual training episode')
            self.assertEqual(meta['first_action_iteration'],1)
            with np.load(Path(d)/'replay.npz') as z:self.assertEqual(len(z['pose']),4)
            r.arm();captured.reset(torch.tensor([0]));self.assertTrue(r.enabled)

    def test_continuous_replay_reports_episode_sum_not_last_reward(self):
        with tempfile.TemporaryDirectory() as d:
            env=FakeEnv();r=Recorder(env,d);r.start()
            env._reward_buf[0]=-.125;env.step(.1)
            env._reward_buf[0]=-.25;env._done_buf[0]=2;env.step(.1)
            r.finish(50,409600,extra_metadata=dict(task='continuous_neutral_pose_mse'))
            p=convert(Path(d)/'replay.npz',dict(names=['pelvis','head'],bones=[[0,1]],shapes=[]),'test')
            self.assertEqual(p['metadata']['evaluation']['episode_mse_m2'],.375)
            self.assertIn('this rollout: 0.375000',p['message'])

    def test_upstream_zero_test_episodes_skips_evaluation(self):
        import ast,time,os
        source=Path(__file__).resolve().parents[2]/'Saved/MimicKit/vendor/MimicKit/mimickit/learning/base_agent.py'
        tree=ast.parse(source.read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='BaseAgent')
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='train_model')
        scope=dict(time=time,os=os);exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),scope)
        class Agent:
            _config={};_iters_per_output=2;_iters_per_log=1;_test_episodes=0
            _env=SimpleNamespace(record_diagnostics=lambda:{})
            _train_return_tracker=SimpleNamespace(reset=lambda:None)
            def __init__(self):self.updates=0;self.resets=0;self.outputs=[]
            def _build_logger(self,*args):return SimpleNamespace(print_log=lambda:None,write_log=lambda:None)
            def _reset_envs(self):self.resets+=1;return None,None
            def _init_train(self):self._sample_count=0;self._iter=0
            def _train_iter(self):self.updates+=1;return {}
            def _update_sample_count(self):return self.updates*32
            def test_model(self,*args):raise AssertionError('unexpected evaluation')
            def _log_train_info(self,train,test,*args):assert test is None
            def _output_train_model(self,it,*args):self.outputs.append(it)
        a=Agent();scope['train_model'](a,96,'unused',False,'tb')
        self.assertEqual(a.updates,3);self.assertEqual(a.outputs,[0,2]);self.assertEqual(a.resets,3)

    def test_checkpoint_is_verified_before_latest_marker(self):
        for corrupt in [False,True]:
            with tempfile.TemporaryDirectory() as d:
                fake=FakeS3(corrupt);path=Path(d)/'checkpoint.zip';path.write_bytes(b'checkpoint')
                with patch('backup.boto3.client',return_value=fake):b=Backups(d,{},'trial')
                b.submit(path)
                if corrupt:
                    with self.assertRaises(RuntimeError):b.wait()
                    self.assertNotIn('trial/latest_verified.json',fake.data)
                else:
                    b.wait();self.assertIn('trial/latest_verified.json',fake.data)

    def test_original_humanoid_geometry(self):
        repo=Path(__file__).resolve().parents[2]/'Saved/MimicKit/vendor/MimicKit'
        g=geometry(repo/'data/assets/humanoid/humanoid.xml')
        self.assertEqual(len(g['names']),15)
        self.assertEqual(len(g['bones']),14)
        feet=[s for s in g['shapes'] if 'foot' in s['bone']]
        self.assertEqual(len(feet),2)
        self.assertTrue(all(s['kind']=='box' for s in feet))

if __name__=='__main__':unittest.main()
