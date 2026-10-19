"""Bounded noisy physics regression from a saved policy; never runs PPO or saves weights."""
import argparse,json,time
from pathlib import Path
from train_local import ROOT,SOURCE,LocalTransferEnv,OmniPPOAgent,mp_util,np,torch,wp,yaml,os
from learning.base_agent import AgentMode


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('run',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--ticks',type=int,default=256)
    parser.add_argument('--worlds',type=int,default=512)
    parser.add_argument('--seed-iterations',type=int)
    args=parser.parse_args();directory=args.run.resolve();out=args.out.resolve()
    assert not out.exists(), 'Preserve previous evidence'
    if args.seed_iterations is not None:
        from optimization_reference import configure_candidate
        configure_candidate(seed_iterations=args.seed_iterations)
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    torch.manual_seed(753);np.random.seed(753)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6732)
    os.chdir(SOURCE/'MimicKit')
    configs={n:yaml.safe_load((directory/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')}
    configs['engine']['transfer_capture_failures']=True
    env=LocalTransferEnv(configs['env'],configs['engine'],args.worlds,'cuda:0',False)
    agent=OmniPPOAgent(configs['agent'],env,'cuda:0');agent.load(str(directory/'model.pt'))
    agent.eval();agent.set_mode(AgentMode.TRAIN)
    obs,info=env.reset();started=time.perf_counter();resets=0
    try:
        for tick in range(args.ticks):
            with torch.no_grad():action,_=agent._decide_action(obs,info)
            obs,reward,done,info=env.step(action)
            env._engine.validate_transfer_solver()
            assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
            ids=done.nonzero(as_tuple=False).flatten();resets+=len(ids)
            if len(ids):obs,info=env.reset(ids)
            if tick%64==63:print('PHYSICS REGRESSION',tick+1,flush=True)
    except BaseException:
        env._engine.failure_capture.save(out.with_suffix('.failure.npz'))
        raise
    contact=env._engine.transfer_contact.p
    result=dict(ticks=args.ticks,worlds=args.worlds,transitions=args.ticks*args.worlds,
        seconds=time.perf_counter()-started,resets=resets,ppo_updates=0,
        solver_failures=0,scalar_fallbacks=int(contact.fallback_count.numpy().sum()),
        scalar_sweeps=int(contact.fallback_steps.numpy().sum()),seed=753,
        solver_seed_iterations=env._engine.transfer_contact.seed_iterations)
    out.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':main()
