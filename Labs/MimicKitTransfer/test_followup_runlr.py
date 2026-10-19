"""Frozen old Unreal Run LR policy/body; isolated candidate timing and motion."""
import argparse,json,time,hashlib,shutil,sys
from pathlib import Path
from train_local import ROOT,SOURCE,LocalTransferEnv,OmniPPOAgent,mp_util,np,torch,wp,yaml,os
from learning.base_agent import AgentMode
from followup_candidates import adapter_class,OUT,generate

def main():
    p=argparse.ArgumentParser();p.add_argument('--kind',default='warm');p.add_argument('--ticks',type=int,default=64)
    p.add_argument('--ppo-shared',action='store_true',help='Compare one identical-data PPO update before old-policy rollouts')
    p.add_argument('--worlds',type=int,default=512);p.add_argument('--label',required=True);p.add_argument('--record',action='store_true');p.add_argument('--once',action='store_true');a=p.parse_args()
    generate();destination=OUT/(a.label+'.json');assert not destination.exists()
    directory=ROOT/'Saved/MimicKitLocal/runs/2026-10-16_02-00_transfer_finetune_512'
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6732);os.chdir(SOURCE/'MimicKit')
    cfg={n:yaml.safe_load((directory/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')}
    body=OUT/'archived-runlr-body';body.mkdir(exist_ok=True)
    for f in (SOURCE/'assets/uefn').iterdir():
        if f.is_file():shutil.copy2(f,body/f.name)
    for f in (ROOT/'Labs/MimicKitUEFN').glob('*.py'):shutil.copy2(f,body/f.name)
    for name in ('humanoid_uefn.xml','limits.json','physics.json'):
        assert (body/name).read_bytes()==(SOURCE/'assets/uefn'/name).read_bytes()
    sys.path[:0]=[str(body),str(ROOT/'Labs/PhysicalRecoveryLab')]
    cfg['env']['char_file']=(body/'humanoid_uefn.xml').as_posix()
    cfg['engine']['uefn_asset_directory']=body.as_posix();cfg['engine']['transfer_capture_failures']=False
    env=LocalTransferEnv(cfg['env'],cfg['engine'],a.worlds,'cuda:0',False)
    agent=OmniPPOAgent(cfg['agent'],env,'cuda:0');agent.load(str(directory/'model.pt'));agent.eval();agent.set_mode(AgentMode.TEST)
    agent._compute_actor_loss=agent._compute_actor_loss_reference
    ppo_reports=[];models={}
    if a.ppo_shared:
        import copy
        from followup_ppo import install
        from resume import restore
        agent._init_train();agent.set_mode(AgentMode.TRAIN);agent._curr_obs,agent._curr_info=agent._reset_envs()
        with torch.no_grad():agent._rollout_train(agent._steps_per_iter)
        agent._build_train_data()
        saved=copy.deepcopy(agent.state_dict());models['original']=saved
        optim={k:copy.deepcopy(getattr(agent,'_'+k+'_optimizer')._optimizer.state_dict()) for k in ('actor','critic')}
        for mode in ('baseline','shared'):
            agent.load_state_dict(saved)
            for k in optim:getattr(agent,'_'+k+'_optimizer')._optimizer.load_state_dict(copy.deepcopy(optim[k]))
            torch.manual_seed(777);agent._exp_buffer._reset_sample_buf()
            remove=install(agent,capture=False) if mode=='shared' else None
            torch.cuda.synchronize();begun=time.perf_counter();metrics=agent._update_model();torch.cuda.synchronize()
            ppo_reports.append(dict(mode=mode,seconds=time.perf_counter()-begun,metrics={k:float(v.detach()) for k,v in metrics.items()}))
            if remove:remove()
            models[mode]=copy.deepcopy(agent.state_dict())
            assert all(torch.isfinite(p).all() for p in agent.parameters())
        agent.eval();agent.set_mode(AgentMode.TEST)
    engine=env._engine;s=engine._solver;m=s.mjw_model;d=s.mjw_data
    custom={'baseline':engine.transfer_contact};graphs={'baseline':engine._graph}
    if a.kind!='baseline':
        if a.kind=='warm':
            from followup_warm_contacts import adapter_class as warm_class
            cls=warm_class()
        else:cls=adapter_class(a.kind)
        c=cls(m,d,s.mj_model,engine._uefn_motors,iterations=100,allow_soft_limits=True,relaxation=.5,hard_limit_control=True,block_motors=True,manifolds=True,jolt_limit_axes=True)
        m.transfer_contact_test=None;c.install();engine.transfer_contact=c;engine._build_graphs();custom[a.kind]=c;graphs[a.kind]=engine._graph
    phases=(torch.arange(a.worlds,device='cuda:0')%16)/16
    duration=float(env._motion_lib.get_motion_lengths()[0]);env._sample_motion_times=lambda n:(torch.zeros(n,dtype=torch.long,device='cuda:0'),phases[:n]*duration)
    rows=[]
    order=['original','baseline','shared'] if a.ppo_shared else [a.kind] if a.once or a.kind=='baseline' else ['baseline',a.kind,a.kind,'baseline']
    for index,kind in enumerate(order):
        if a.ppo_shared:agent.load_state_dict(models[kind])
        physics='baseline' if a.ppo_shared else kind
        engine.transfer_contact=custom[physics];engine._graph=graphs[physics];m.transfer_contact_test=custom[physics]
        c=custom[physics];c.p.warm_state.zero_()
        if hasattr(c,'cache'):c.cache.count.zero_();c.cache.group_count.zero_()
        torch.manual_seed(753);np.random.seed(753);obs,info=env.reset()
        engine._sim_state.pre_step_update();engine._body_velocity.update(engine._sim_state.raw_state)
        def state():
            raw=engine._sim_state.raw_state
            return np.concatenate([raw.body_q.numpy().reshape(a.worlds,15,7),raw.body_qd.numpy().reshape(a.worlds,15,6)],-1)
        arrays=dict(initial=state(),states=[],obs=[],actions=[],targets=[],dist=[])
        done_first=torch.zeros(a.worlds,device='cuda:0',dtype=torch.long);flag_first=done_first.clone();peak=torch.zeros(a.worlds,device='cuda:0');times=[]
        warnings_before=int(c.p.convergence_warnings.numpy().sum()+c.p.roundoff_warnings.numpy().sum())
        for tick in range(a.ticks):
            torch.cuda.synchronize();start=time.perf_counter()
            with torch.no_grad():action,_=agent._decide_action(obs,info)
            if a.record:arrays['obs'].append(obs.cpu().numpy().copy());arrays['actions'].append(action.cpu().numpy().copy())
            obs,_,done,info=env.step(action)
            torch.cuda.synchronize();times.append(time.perf_counter()-start)
            distance=env.target_distances_sq.sqrt().amax(dim=-1);peak=torch.maximum(peak,distance)
            new=(done!=0)&(done_first==0);done_first[new]=tick+1;flag_first[new]=done[new].long()
            if a.record:
                arrays['states'].append(state());arrays['targets'].append(torch.cat([env.reward_target_pos,env.reward_target_rot],-1).cpu().numpy().copy());arrays['dist'].append(env.target_distances_sq.sqrt().cpu().numpy().copy())
            if tick%60==59:print(kind,'tick',tick+1,flush=True)
        warning=engine.validate_transfer_solver()
        assert torch.isfinite(obs).all()
        row=dict(kind=kind,first_done=done_first.cpu().tolist(),first_flags=flag_first.cpu().tolist(),max_distance=peak.cpu().tolist(),mean_tick_seconds=float(np.mean(times[8:])),median_tick_seconds=float(np.median(times[8:])),warning_delta=int(c.p.convergence_warnings.numpy().sum()+c.p.roundoff_warnings.numpy().sum())-warnings_before,warning=warning)
        rows.append(row);print(json.dumps({k:v for k,v in row.items() if k not in ('first_done','first_flags','max_distance','warning')}),flush=True)
        if a.record:np.savez_compressed(OUT/(a.label+'_'+str(index)+'.npz'),**arrays)
        report=dict(checkpoint=str(directory/'model.pt'),checkpoint_sha256=hashlib.sha256((directory/'model.pt').read_bytes()).hexdigest(),body_directory=str(SOURCE/'assets/uefn'),worlds=a.worlds,ticks=a.ticks,runs=rows,disposable_ppo=ppo_reports)
        destination.write_text(json.dumps(report,indent=2))
if __name__=='__main__':main()
