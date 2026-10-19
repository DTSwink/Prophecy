"""Bounded local trajectory search. No policy weights or training files change.

Find a physical witness, if one exists, using only velocity commands. A failed
search proves nothing about impossibility. The actor is frozen throughout.
"""
import json,time
import numpy as np
import torch


def search(env,agent,path,args,motion):
    started=time.perf_counter();device=env._device;n=env.get_num_envs()
    assert n>=64
    # Torso and legs: arms keep the frozen policy's outputs.
    indices=[]
    model=env._kin_char_model
    for j in range(1,model.get_num_joints()):
        name=model.get_body_name(j)
        if name=='torso' or any(part in name for part in ['thigh','shin','foot']):
            lo=model.get_joint(j).dof_idx
            hi=model.get_joint(j+1).dof_idx if j+1<model.get_num_joints() else model.get_dof_size()
            indices.extend(range(lo,hi))
    indices=torch.tensor(indices,device=device)
    horizon=round(args.seconds*30);knots=(horizon+2)//3;k=len(indices)
    mean=torch.zeros(knots,k,device=device);sigma=torch.full_like(mean,3.)
    best=mean.clone();history=[];start_ticks=6
    if args.search_seed:
        seed=np.load(args.search_seed)
        np.testing.assert_array_equal(seed['indices'],indices.cpu().numpy())
        old=torch.as_tensor(seed['offsets'],device=device)
        count=min(len(old),knots);mean[:count]=old[:count];best=mean.clone();sigma[:count]=.3
        start_ticks=min(count*3,horizon)

    def evaluate(parameters,ticks,capture=False):
        obs,_=env.reset();totals=torch.zeros(n,device=device);worst=totals.clone();first=torch.full_like(totals,ticks/30)
        active=torch.ones(n,dtype=torch.bool,device=device);states=[];targets=[];commands=[]
        for tick in range(ticks):
            with torch.no_grad():cmd,_=agent._decide_action(obs,{})
            cmd[:,indices]+=parameters[:,tick//3]
            cmd=torch.maximum(torch.minimum(cmd,env._action_bound_high),env._action_bound_low)
            obs,_,done,_=env.step(cmd)
            dist=env.target_distances_sq.sqrt().amax(-1)
            totals+=env.loss_terms.sum(-1)
            worst=torch.maximum(worst,dist)
            failed=(done==1)&active;first[failed]=(tick+1)/30;active[failed]=False
            if capture:
                char=env._get_char_id();e=env._engine
                states.append(torch.cat([e.get_body_pos(char)[:1],e.get_body_rot(char)[:1]],-1).cpu().numpy())
                targets.append(torch.cat([env.reward_target_pos[:1],env.reward_target_rot[:1]],-1).cpu().numpy())
                commands.append(cmd[:1].cpu().numpy())
        score=totals/ticks+40*torch.clamp(worst-.25,min=0).square()+2*(ticks/30-first)+1000*(~active)
        return score,first,worst,active,(states,targets,commands)

    stages=list(range(start_ticks,horizon,6))+[horizon]
    for ticks in stages:
        used=(ticks+2)//3
        if args.search_windowed:
            # Keep the established prefix; optimize only the last 0.4 seconds.
            # This is an offline trajectory search, not a change to the policy.
            mean=best.clone();sigma[max(0,used-4):used].clamp_(min=.7)
        for iteration in range(8):
            if args.search_windowed:sigma[:max(0,used-4)]=0
            candidates=mean+sigma*torch.randn(n,knots,k,device=device)
            candidates[0]=best;candidates[1]=mean
            score,seconds,dist,passed,_=evaluate(candidates,ticks)
            values,elite=torch.topk(score,max(8,n//16),largest=False)
            best=candidates[elite[0]].clone()
            mean[:used]=.2*mean[:used]+.8*candidates[elite,:used].mean(0)
            sigma[:used]=(.3*sigma[:used]+.7*candidates[elite,:used].std(0)).clamp(min=.3)
            row=dict(ticks=ticks,iteration=iteration,cost=float(values[0]),seconds=float(seconds[elite[0]]),
                max_distance_m=float(dist[elite[0]]),passed_candidates=int(passed.sum()),elapsed_seconds=time.perf_counter()-started)
            history.append(row);print('SEARCH',json.dumps(row),flush=True)
        # If even the short horizon cannot be sustained, avoid spending on a
        # much longer search. This is inconclusive, never "motors too weak".
        if not bool(passed.any()):break
    for name in ['audit_peak','audit_capped','audit_speed','audit_count']:getattr(env._engine,name).zero_()
    for name in ['roundoff_warnings','roundoff_delta','convergence_warnings','convergence_metrics']:
        getattr(env._engine.transfer_contact.p,name).zero_()
    score,seconds,dist,passed,traces=evaluate(best[None].expand(n,-1,-1),ticks,capture=True)
    warning=env._engine.validate_transfer_solver()
    report=dict(motion=motion,settings=vars(args),history=history,seconds=float(seconds[0]),
        requested_horizon_seconds=ticks/30,passed=bool(passed[0]),max_distance_m=float(dist[0]),
        reproducibility_range_m=[float(dist.min()),float(dist.max())],repeat_passed=int(passed.sum()),repeat_count=n,
        delivered_peak_torque_nm=env._engine.audit_peak.numpy()[0].tolist(),
        torque_caps_nm=env._engine._uefn_motors.upper.numpy().tolist(),
        solver_warning=warning,solver_metrics_row0=env._engine.transfer_contact.p.convergence_metrics.numpy()[0].tolist(),
        elapsed_seconds=time.perf_counter()-started,
        method='Frozen policy plus optimized torso/leg velocity offsets, exact deployed physics, free root. No policy update, root force or contact pin.',
        limitations='A successful trace is only a witness for its tested initial state/duration. Failed bounded search is not evidence of insufficient motor strength.')
    path.write_text(json.dumps(report,indent=2))
    np.savez_compressed(path.with_suffix('.npz'),pose=traces[0],target=traces[1],commands=traces[2],offsets=best.cpu().numpy(),indices=indices.cpu().numpy())
    print('RESULT',json.dumps({k:report[k] for k in ['seconds','passed','max_distance_m','elapsed_seconds']}),flush=True)
