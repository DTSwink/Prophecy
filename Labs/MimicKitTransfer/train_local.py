"""Bounded local transfer fine-tuning, using upstream PPO and verified archive.

No cloud calls. Only one rolling local checkpoint; original archive untouched.
The full omni experiment remains gated on native transfer verification.
"""
import argparse,hashlib,json,os,random,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'Saved/MimicKitTransfer/no-armature-3913/source'
os.environ.setdefault('PYGLET_HEADLESS','true')
os.environ.setdefault('OMP_NUM_THREADS','1')
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(ROOT/'Labs/MimicKitTraining'),
             str(SOURCE/'MimicKit/mimickit')]
import numpy as np,torch,warp as wp,yaml
from omni_walk import OmniWalkEnv
from omni_policy import OmniPPOAgent
from contact_engine import ContactTransferEngine
from resume import restore
from health import install_guard
from util import mp_util


class LocalTransferEnv(OmniWalkEnv):
    def _build_engine(self,config,num_envs,device,visualize,record_video=False):
        return ContactTransferEngine(config,num_envs,device,visualize,record_video)


def atomic_json(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(path)


def save_checkpoint(agent,directory,iteration):
    # Called only after a fully validated PPO update.
    model=directory/'model.tmp.pt';agent.save(str(model));model.replace(directory/'model.pt')
    state=dict(completed_iteration=iteration,samples=agent._sample_count,
        actor_optimizer=agent._actor_optimizer._optimizer.state_dict(),
        critic_optimizer=agent._critic_optimizer._optimizer.state_dict(),
        actor_steps=agent._actor_optimizer._steps,critic_steps=agent._critic_optimizer._steps,
        torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all(),
        numpy_rng=np.random.get_state(),python_rng=random.getstate(),
        normalizer_aux={name:{k:getattr(mod,k) for k in ('_mean_sq','_new_count','_new_sum','_new_sum_sq')}
            for name,mod in agent.named_modules() if hasattr(mod,'_new_sum_sq')},physics_episode_state_saved=False)
    torch.save(state,directory/'resume_state.pt')
    temp=directory/'latest.tmp.zip'
    with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_STORED) as archive:
        for name in ('model.pt','resume_state.pt','env_config.yaml','engine_config.yaml','agent_config.yaml','provenance.json'):
            archive.write(directory/name,name)
    digest=hashlib.sha256(temp.read_bytes()).hexdigest()
    with zipfile.ZipFile(temp) as archive:assert archive.testzip() is None
    temp.replace(directory/'latest.zip')
    atomic_json(directory/'checkpoint.json',dict(iteration=iteration,samples=agent._sample_count,
        sha256=digest,file='latest.zip',verified=True))


def main():
    parser=argparse.ArgumentParser()
    start=parser.add_mutually_exclusive_group(required=True)
    start.add_argument('--resume',type=Path)
    start.add_argument('--prepared',type=Path,help='Fresh all-motion training; requires verified native report')
    parser.add_argument('--transfer-report',type=Path)
    parser.add_argument('--worlds',type=int,default=512)
    parser.add_argument('--updates',type=int,default=100)
    parser.add_argument('--name',required=True)
    args=parser.parse_args()
    assert args.updates>0 and args.worlds>=4
    archive=args.resume.resolve() if args.resume else None
    prepared=args.prepared.resolve() if args.prepared else None
    if prepared:
        assert args.transfer_report,'Fresh omni training requires completed native verification'
        verification=json.loads(args.transfer_report.read_text())
        assert verification['accepted'] and verification['native_successes']==verification['native_starts']
        assert verification['native_starts']>=16 and verification['ticks']>=300
        for name,digest in verification['sha256'].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,('Verification input changed',name)
    directory=ROOT/'Saved/MimicKitLocal/runs'/args.name
    directory.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6732)
    os.chdir(SOURCE/'MimicKit')
    if archive:
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            configs={name:yaml.safe_load(z.read(name+'_config.yaml').decode().replace(
                '/workspace/mimickit_trial',SOURCE.as_posix())) for name in ('env','engine','agent')}
    else:
        configs={name:yaml.safe_load((prepared/(name+'_config.yaml')).read_text()) for name in ('env','engine','agent')}
    configs['env']['char_file']=(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml').as_posix()
    configs['engine']['uefn_asset_directory']=(ROOT/'Labs/MimicKitUEFN').as_posix()
    configs['engine']['transfer_capture_failures']=True
    # Evaluation is done separately on the exact 16-phase MJ/native matrix.
    # This affects logging only, not PPO, rewards, resets or exploration.
    configs['agent'].update(test_episodes=32 if prepared else 0,iters_per_output=100 if prepared else 25,iters_per_log=1)
    for name,config in configs.items():(directory/(name+'_config.yaml')).write_text(yaml.safe_dump(config,sort_keys=False))
    atomic_json(directory/'owner.json',dict(pid=os.getpid(),worlds=args.worlds,updates=args.updates))
    atomic_json(directory/'provenance.json',dict(resume=str(archive) if archive else None,
        resume_sha256=hashlib.sha256(archive.read_bytes()).hexdigest() if archive else None,
        task='local fresh omni plus idle' if prepared else 'local Run LR transfer fine-tuning',worlds=args.worlds,updates=args.updates,
        physics='bounded motors; hard Jolt contact/manifold friction and angular limits; split position projection',
        remaining_difference='reduced versus maximal coordinate finite-step articulation',
        gpu=torch.cuda.get_device_name(0),fresh_physical_episodes=True,
        started_unix=time.time(),prepared=str(prepared) if prepared else None,
        transfer_verification=str(args.transfer_report) if args.transfer_report else None))
    env=LocalTransferEnv(configs['env'],configs['engine'],args.worlds,'cuda:0',False)
    agent=OmniPPOAgent(configs['agent'],env,'cuda:0')
    resumed=restore(agent,archive) if archive else dict(prior_samples=0,iteration_offset=0,fresh_weights=True)
    atomic_json(directory/'resume.json',resumed)
    assert env._engine._graph is not None
    # Shared guard rejects latched solver failures before PPO, once per rollout.
    def report_failure(detail):
        atomic_json(directory/'numerical_failure.json',dict(detail,iteration=agent._iter,time=time.time()))
        print('TRAINING ALERT: '+json.dumps(detail),flush=True)
    install_guard(agent,report_failure)
    train=agent._train_iter;timings=[];started=time.perf_counter();last_complete=-1
    tb=ROOT/'Saved/MimicKit/TensorBoardRuns'/args.name
    tb.mkdir(parents=True,exist_ok=False)
    from torch.utils.tensorboard import SummaryWriter
    writer=SummaryWriter(str(tb))
    viewer=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs')/('mimickit_local_'+args.name)/'debug'
    if prepared:
        from observe import Recorder
        # The PHAT adapter also exposes its sibling recovery utilities on
        # sys.path. Load this viewer adapter explicitly to avoid replay.py
        # colliding with that unrelated module.
        import importlib.util
        spec=importlib.util.spec_from_file_location('local_omni_replay',ROOT/'Labs/MimicKitTraining/replay.py')
        replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)
        convert,geometry=replay.convert,replay.geometry
        recorder=Recorder(env,directory);recorder.phase_agent=agent
        geom=geometry(Path(configs['env']['char_file']))
        viewer.mkdir(parents=True,exist_ok=False)
        atomic_json(viewer/'training.active.json',dict(pid=os.getpid(),kind='local_mimickit'))
        evaluate=agent._rollout_test
        def recorded_evaluation(episodes):
            totals=env._completed_loss_totals.clone();env._completed_loss_totals.zero_()
            recorder.start()
            try:result=evaluate(episodes)
            finally:recorder.enabled=False
            env._engine.validate_transfer_solver()
            losses=env.take_completed_losses();env._completed_loss_totals.copy_(totals)
            recorder.finish(resumed['iteration_offset']+agent._iter,agent._sample_count,
                dict(training_action_noise_std=float(configs['agent']['model']['action_std']),rollout_action_noise_std=0.,
                     worlds=args.worlds,control_mode='vel',losses=losses or {}))
            payload=convert(directory/'replay.npz',geom,'mimickit_local_'+args.name)
            atomic_json(viewer/'last_batch_rollout.json',payload)
            atomic_json(directory/'evaluation.json',dict(result,losses=losses,iteration=agent._iter,samples=agent._sample_count))
            if losses:
                for name,value in losses.items():writer.add_scalar('test/'+name,value,agent._sample_count)
            writer.flush()
            return result
        agent._rollout_test=recorded_evaluation
    def update():
        nonlocal last_complete
        if (directory/'stop.request').exists():raise InterruptedError('Requested stop before next PPO update')
        begin=time.perf_counter();result=train();torch.cuda.synchronize()
        if not bool(torch.stack([torch.isfinite(p).all() for p in agent.parameters()]).all()):
            raise FloatingPointError('Invalid model after PPO; previous checkpoint retained')
        elapsed=time.perf_counter()-begin;timings.append(elapsed);last_complete=agent._iter
        samples=resumed['prior_samples']+(agent._iter+1)*args.worlds*agent._steps_per_iter
        losses=env.take_completed_losses()
        if losses:
            for key,value in losses.items():writer.add_scalar('loss/'+key,value,samples)
        for key in ('actor_loss','critic_loss','phase_prediction_mse'):
            if key in result:writer.add_scalar('optimizer/'+key,float(result[key]),samples)
        writer.add_scalar('episode/length_seconds',float(result['mean_ep_len'])/30,samples)
        writer.add_scalar('performance/transitions_per_second',args.worlds*agent._steps_per_iter/elapsed,samples)
        writer.flush()
        status=dict(state='training',completed_updates=agent._iter+1,iteration=resumed['iteration_offset']+agent._iter,
            samples=samples,worlds=args.worlds,update_seconds=elapsed,mean_update_seconds=float(np.mean(timings[-10:])),
            transitions_per_second=args.worlds*agent._steps_per_iter/float(np.mean(timings[-10:])),
            elapsed_seconds=time.perf_counter()-started,losses=losses,episode_ticks=float(result['mean_ep_len']))
        solver=env._engine.transfer_contact.p
        status.update(scalar_fallbacks=int(solver.fallback_count.numpy().sum()),
                      scalar_fallback_iterations=int(solver.fallback_steps.numpy().sum()))
        atomic_json(directory/'status.json',status);print('LOCAL_UPDATE '+json.dumps(status),flush=True)
        return result
    agent._train_iter=update
    agent._output_train_model=lambda it,*unused:save_checkpoint(agent,directory,resumed['iteration_offset']+it)
    try:
        agent.train_model(resumed['prior_samples']+args.updates*args.worlds*agent._steps_per_iter,str(directory),False,'txt')
        state='completed'
    except InterruptedError:
        state='stopped'
        if last_complete>=0:save_checkpoint(agent,directory,resumed['iteration_offset']+last_complete)
    except BaseException as error:
        capture=env._engine.failure_capture
        if int(capture.seen.numpy()[0]):capture.save(directory/'first_failed_equations.npz')
        atomic_json(directory/'failure.json',dict(error=repr(error),last_completed_update=last_complete,time=time.time()))
        raise
    finally:
        writer.close()
        if prepared:(viewer/'training.active.json').unlink(missing_ok=True)
    status=json.loads((directory/'status.json').read_text());status['state']=state
    atomic_json(directory/'status.json',status)


if __name__=='__main__':main()
