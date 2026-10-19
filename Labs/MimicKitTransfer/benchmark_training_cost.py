"""Disposable full PPO-update timing; no checkpoint, TensorBoard or replay writes."""
import argparse,json,time
from pathlib import Path
from train_local import ROOT,SOURCE,LocalTransferEnv,OmniPPOAgent,mp_util,np,torch,wp,yaml,os
from engines.newton_engine import NewtonEngine


class VanillaEngine(NewtonEngine):
    def _build_solver(self):
        # Match the current body's physical inertia; no extra armature.
        self._sim_model.joint_armature.zero_()
        super()._build_solver()


class VanillaEnv(LocalTransferEnv):
    def _build_engine(self,config,*args,**kwargs):return VanillaEngine(config,*args,**kwargs)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['vanilla','profile','reference','paired','all'])
    parser.add_argument('--out',type=Path)
    parser.add_argument('--seed-iterations',type=int)
    parser.add_argument('--reference-folder',type=Path)
    args=parser.parse_args()
    if args.reference_folder:args.reference_folder=args.reference_folder.resolve()
    run=ROOT/'Saved/MimicKitLocal/runs/2026-10-16_02-07-18_omni_idle_fresh_512'
    out=args.out.resolve() if args.out else ROOT/'Saved/MimicKitLocal/performance_vanilla'/('update_'+args.mode+'.json')
    assert not out.exists()
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(753);np.random.seed(753)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6732);os.chdir(SOURCE/'MimicKit')
    configs={n:yaml.safe_load((run/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')}
    configs['engine']['transfer_capture_failures']=False
    import contact_engine
    from optimization_reference import components,configure_candidate
    current=(contact_engine.SequentialContactAdapter,contact_engine.SplitLimitProjection)
    recorded={}
    def instrument(obj,name,label):
        original=getattr(obj,name)
        def call(*a,**kw):
            start=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
            start.record();result=original(*a,**kw);end.record()
            recorded.setdefault(label,[]).append((start,end));return result
        setattr(obj,name,call)
    modes=['vanilla','reference','profile'] if args.mode=='all' else ['reference','profile'] if args.mode=='paired' else [args.mode]
    agents={};rows_by_mode={mode:[] for mode in modes};rng={}
    for mode in modes:
        torch.manual_seed(753);np.random.seed(753)
        contact_engine.SequentialContactAdapter,contact_engine.SplitLimitProjection=components(args.reference_folder) if mode=='reference' else current
        if mode=='profile' and args.seed_iterations is not None:configure_candidate(args.seed_iterations)
        cls=VanillaEnv if mode=='vanilla' else LocalTransferEnv
        env=cls(configs['env'],configs['engine'],512,'cuda:0',False)
        agent=OmniPPOAgent(configs['agent'],env,'cuda:0');agent.load(str(run/'model.pt'))
        agent._curr_obs,agent._curr_info=agent._reset_envs();agent._init_train()
        for obj,name,label in [(env._engine,'step','physics'),(agent,'_decide_action','policy'),
                              (agent,'_update_actor','actor_update'),(agent,'_update_critic','critic_update'),
                              (agent,'_build_train_data','training_data')]:instrument(obj,name,label)
        agents[mode]=(env,agent);rng[mode]=(torch.get_rng_state(),torch.cuda.get_rng_state())
    for i in range(6):
        for mode in modes if i%2==0 else list(reversed(modes)):
            env,agent=agents[mode];torch.set_rng_state(rng[mode][0]);torch.cuda.set_rng_state(rng[mode][1])
            recorded.clear();torch.cuda.synchronize();start=time.perf_counter()
            result=agent._train_iter();torch.cuda.synchronize();wall=time.perf_counter()-start
            if mode!='vanilla':env._engine.validate_transfer_solver()
            assert torch.isfinite(agent._curr_obs).all()
            row=dict(update=i,wall_seconds=wall,mean_episode_ticks=float(result['mean_ep_len']),
                gpu_ms={label:sum(a.elapsed_time(b) for a,b in events) for label,events in recorded.items()})
            rows_by_mode[mode].append(row);agent._iter+=1;rng[mode]=(torch.get_rng_state(),torch.cuda.get_rng_state())
            print(mode,json.dumps(row),flush=True)
    summaries={}
    for mode,rows in rows_by_mode.items():
        summaries[mode]=dict(mode=mode,worlds=512,steps_per_update=32,rows=rows,
        median_update_seconds=float(np.median([r['wall_seconds'] for r in rows[1:]])),
        median_gpu_ms={label:float(np.median([r['gpu_ms'][label] for r in rows[1:]])) for label in recorded},
        scope='Same checkpoint/network/PPO/body/timestep, six disposable updates; first excluded. Engine physics differ, therefore contacts/resets differ. No saved weights or production training resumed.',
        evaluation_checkpoint_io_included=False)
    report=summaries[args.mode] if args.mode not in ('paired','all') else dict(mode=args.mode,alternating_order=True,results=summaries,
        sampled_median_ratio=summaries['reference']['median_update_seconds']/summaries['profile']['median_update_seconds'],
        timing_range_ratio={mode:max(r['wall_seconds'] for r in rows[1:])/min(r['wall_seconds'] for r in rows[1:]) for mode,rows in rows_by_mode.items()},
        caution='A timing ratio is not a causal speedup when external GPU/CPU load varies; inspect ranges and unchanged policy/optimizer timings.',
        per_round_speedups=[r['wall_seconds']/p['wall_seconds'] for r,p in zip(rows_by_mode['reference'][1:],rows_by_mode['profile'][1:])])
    if args.mode=='all':
        report['profile_to_vanilla_ratio']=summaries['profile']['median_update_seconds']/summaries['vanilla']['median_update_seconds']
    out.write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


if __name__=='__main__':main()
