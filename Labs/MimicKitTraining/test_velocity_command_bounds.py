"""Check widened commands and exact checkpoint preservation; optional local PPO smoke."""
import argparse, io, json, math, os, sys, time, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'Saved/MimicKitMotorAudit/source'
sys.path[:0] = [str(ROOT/'Saved/MimicKitUEFN/dependencies'), str(Path(__file__).parent),
               str(SOURCE/'MimicKit/mimickit')]
os.environ['PYGLET_HEADLESS'] = 'true'
os.environ['OMP_NUM_THREADS'] = '1'
import numpy as np
import torch, yaml
from gymnasium.spaces import Box
from learning.normalizer import Normalizer
from omni_policy import OmniPPOAgent, OmniPPOModel


def main():
    p=argparse.ArgumentParser();p.add_argument('--physics',action='store_true')
    p.add_argument('--checkpoint',type=Path);p.add_argument('--torque-envelope',type=Path);a=p.parse_args()
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    output=ROOT/'Saved/MimicKitEquipment'/('torque-limit-check' if a.torque_envelope else 'command-limit-check');output.mkdir(exist_ok=True)
    archive=a.checkpoint.resolve() if a.checkpoint else ROOT/'Saved/MimicKitEquipment/latest-stopped.zip'
    with zipfile.ZipFile(archive) as z:
        saved=torch.load(io.BytesIO(z.read('model.pt')),map_location='cpu',weights_only=True)
        configs={n:yaml.safe_load(z.read(n+'_config.yaml')) for n in ('env','engine','agent')}
    envelope=json.loads((ROOT/'Saved/MimicKitMotorAudit/command-envelope.json').read_text())
    high=torch.tensor([max(2*math.pi,1.05*r['command_bound_rad_s']) for r in envelope['rows']])
    torque=None
    if a.torque_envelope:
        torque=json.loads(a.torque_envelope.read_text())
        base=torch.tensor(torque['base_caps_nm']);new=torch.tensor(torque['applied_caps_nm']);gains=torch.tensor(torque['base_gains'])
        # Existing report holds reference speed + old cap/gain before the 5% margin.
        required=torch.tensor([r['command_bound_rad_s'] for r in envelope['rows']])+(new-base)/gains
        high=torch.maximum(torch.full_like(required,2*math.pi),1.05*required)
        configs['engine']['uefn_motor_torque_caps_nm']=torque['overrides_nm']
    class Spaces:
        _action_bound_high=high
        _action_bound_low=-high
        def get_obs_space(self):return Box(-np.inf,np.inf,(154,))
        def get_action_space(self):return Box(-high.numpy(),high.numpy())
    class Holder:pass
    h=Holder();h._env=Spaces()
    h._a_norm=Normalizer((34,),device='cpu',init_mean=saved['_a_norm._mean'],init_std=saved['_a_norm._std'])
    dist=Holder();dist.mode=torch.full((3,34),1.01,requires_grad=True)
    limits=h._a_norm.normalize(high)
    dist.mode=torch.stack([torch.zeros(34),limits*.99,-limits*.99]).requires_grad_()
    penalty=OmniPPOAgent._compute_action_bound_loss(h,dist)
    assert torch.equal(penalty,torch.zeros(3))
    dist.mode=torch.stack([limits+.1,-limits-.1]).requires_grad_()
    loss=OmniPPOAgent._compute_action_bound_loss(h,dist);loss.sum().backward()
    assert torch.all(loss>0) and torch.all(dist.mode.grad[0]>0) and torch.all(dist.mode.grad[1]<0)
    # Old bounds reproduce the upstream penalty exactly.
    h._env._action_bound_high=torch.full((34,),2*math.pi);h._env._action_bound_low=-h._env._action_bound_high
    dist.mode=torch.randn(256,34)*2
    expected=((dist.mode+1).clamp_max(0).square()+(dist.mode-1).clamp_min(0).square()).sum(-1)
    torch.testing.assert_close(OmniPPOAgent._compute_action_bound_loss(h,dist),expected,rtol=0,atol=0)
    report=dict(cpu_passed=True,normalization_changed=False,physical_noise_std_rad_s=float(saved['_a_norm._std'][0]*.05),
                permitted_normalized_range=[float(limits.min()),float(limits.max())])
    if a.physics:
        import warp as wp
        from util import mp_util
        from omni_walk import OmniWalkEnv
        from resume import restore
        from learning.base_agent import AgentMode
        os.chdir(SOURCE/'MimicKit');wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6757)
        cfg={n:yaml.safe_load(yaml.safe_dump(v).replace('/workspace/mimickit_trial',SOURCE.as_posix())) for n,v in configs.items()}
        motionfile=output/'motions.yaml'
        motionfile.write_text((SOURCE/'prepared/motions.yaml').read_text().replace('/workspace/mimickit_trial',SOURCE.as_posix()))
        cfg['env']['motion_file']=str(motionfile);cfg['env']['velocity_command_margin']=.05
        begun=time.perf_counter();env=OmniWalkEnv(cfg['env'],cfg['engine'],512,'cuda:0',False)
        agent=OmniPPOAgent(cfg['agent'],env,'cuda:0');receipt=restore(agent,archive)
        for key,value in agent.state_dict().items():
            assert torch.equal(value.cpu(),saved[key]),'Checkpoint tensor changed: '+key
        torch.testing.assert_close(env._action_bound_high.cpu(),high,rtol=1e-6,atol=1e-6)
        if torque:
            np.testing.assert_allclose(env._engine._uefn_motors.upper.numpy(),torque['applied_caps_nm'],rtol=1e-6)
            np.testing.assert_array_equal(env._engine._uefn_motors.gains.numpy(),torque['base_gains'])
            report['torque_envelope']=env._engine.torque_envelope_report
        agent._init_train();agent._curr_obs,agent._curr_info=agent._reset_envs()
        agent.eval();agent.set_mode(AgentMode.TRAIN)
        timings=[]
        for _ in range(3):
            start=time.perf_counter()
            with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
            agent._build_train_data();info=agent._update_model()
            torch.cuda.synchronize();timings.append(time.perf_counter()-start)
            assert all(torch.isfinite(v).all() for v in agent.parameters())
            assert all(torch.isfinite(v).all() for v in agent._exp_buffer._buffers.values())
        env._engine.validate_transfer_solver()
        report.update(physics_passed=True,worlds=512,disposable_updates=3,update_seconds=timings,
            exact_checkpoint_tensor_equality=True,resume=receipt,bounds=env.velocity_command_report,
            elapsed_seconds=time.perf_counter()-begun)
    (output/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


if __name__=='__main__':main()
