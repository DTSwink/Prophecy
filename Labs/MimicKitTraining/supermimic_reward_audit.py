"""Bounded real-simulator verification of exact task scoring and its derivatives."""
import json,time,hashlib
import torch
from torch.nn import functional as F
import supermimic_race as base
from supermimic_exact_reward import ExactReward
from supermimic_decoupled import anchor


def audit(env,agent,ctx,wm,out,horizon):
    import mujoco_warp as mjw
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    started=time.perf_counter();n=env.get_num_envs();device=ctx.device
    for p in agent.parameters():p.requires_grad_(False)
    for p in wm.parameters():p.requires_grad_(False)
    agent.eval();agent.set_mode(AgentMode.TEST);exact=ExactReward(ctx)
    result=dict(kind='exact_reward_audit',horizon=horizon,complete=False,validation=[],reset_checks=[],probes=[],
                context_captured_before_rollout=True)

    def reset(s):
        base.seed(s);mjw.reset_data(env._engine._solver.mjw_model,env._engine._solver.mjw_data)
        obs,info=agent._reset_envs()
        xy=env._engine.get_root_pos(env._get_char_id())[:,:2].clone()
        h=ctx.physical(obs)[:,None].repeat(1,3,1);xh=xy[:,None].repeat(1,3,1)
        return obs,info,h,xh

    # Locate the first-reset discrepancy and prime all lazy simulator tensors.
    first=None
    for i in range(4):
        obs,info,h,xh=reset(481031)
        if first is None:first=obs.clone()
        per=(obs-first).abs().amax(0)
        result['reset_checks'].append(dict(repeat=i,sha256=hashlib.sha256(obs.cpu().numpy().tobytes()).hexdigest(),
            max_difference=float(per.max()),changed_channels=(per>1e-6).nonzero().flatten().cpu().tolist(),
            per_channel_max=per.cpu().tolist()))
        with torch.no_grad():env.step(agent._decide_action(obs,info)[0])
    print('REWARD_AUDIT_RESETS',json.dumps(result['reset_checks']),flush=True)

    def step(obs,info,h,xh,delta=None):
        with torch.no_grad():
            action,_=agent._decide_action(obs,info)
            if delta is not None:
                action=agent._a_norm.unnormalize((agent._a_norm.normalize(action)+delta).clamp(ctx.low,ctx.high))
            nxt,reward,done,info=env.step(action)
            xy=env._engine.get_root_pos(env._get_char_id())[:,:2].clone()
            nh=torch.cat((h[:,1:],ctx.physical(nxt)[:,None]),1)
            nxh=torch.cat((xh[:,1:],xy[:,None]),1)
            data=dict(next_x=ctx.physical(nxt).clone(),next_xy=xy,next_phase=nxt[:,-2:].clone(),
                age=torch.round(env._time_buf*30).clone(),times=(env._time_buf+env._motion_time_offsets).clone(),
                reward=reward.clone(),done=(done!=DoneFlags.NULL.value),fail=(done==DoneFlags.FAIL.value),
                terms=env.loss_terms.clone())
            obs,info=agent._reset_done_envs(done)
            ended=data['done'];nh[ended]=ctx.physical(obs)[ended,None].repeat(1,3,1)
            nxh[ended]=env._engine.get_root_pos(env._get_char_id())[ended,None,:2].repeat(1,3,1)
        return obs,info,nh,nxh,data

    def prefix(s,ticks):
        obs,info,h,xh=reset(s);alive=torch.ones(n,device=device,dtype=torch.bool)
        for _ in range(ticks):
            obs,info,h,xh,d=step(obs,info,h,xh);alive &= ~d['done']
        return obs,info,h,xh,alive

    # Compare each weighted loss, velocities and poses before using derivatives.
    obs,info,h,xh=reset(91777)
    for tick in range(1,82):
        old_h,old_xh=h,xh
        motion=env._motion_ids.clone();pert=env._perturbed_rows.clone()
        obs,info,h,xh,d=step(obs,info,h,xh)
        if tick not in [1,2,8,30,40,60,80]:continue
        nh=torch.cat((old_h[:,1:],d['next_x'][:,None]),1)
        nxh=torch.cat((old_xh[:,1:],d['next_xy'][:,None]),1)
        with torch.no_grad():
            predicted,terms=exact(nh,nxh,motion,d['next_phase'],d['age'],d['times'],pert)
            penalty=pert*(env._gaits[motion]!=-1)*float(env._perturb_cfg['loco_failure_penalty'])
            expected=d['reward']+penalty*d['fail']
            error=(terms-d['terms']).abs()
            row=dict(tick=tick,reward_max_error=float((predicted-expected).abs().max()),
                reward_mean_error=float((predicted-expected).abs().mean()),
                terms={name:dict(max=float(error[:,i].max()),mean=float(error[:,i].mean()),
                    actual_mean=float(d['terms'][:,i].mean())) for i,name in enumerate(env.loss_term_names)})
        result['validation'].append(row);base.write(out/'result.json',result)
        print('REWARD_AUDIT_VALIDATION',json.dumps(row),flush=True)
    maximum=max(r['reward_max_error'] for r in result['validation'])
    mean=max(r['reward_mean_error'] for r in result['validation'])
    # Small FK projection rounding is expected; wrong scoring must stop the audit.
    if maximum>0.002 or mean>0.0002:
        result.update(complete=True,passed=False,stop_reason='Exact reward does not match simulator',seconds=time.perf_counter()-started)
        base.write(out/'result.json',result);print('REWARD_AUDIT_COMPLETE',json.dumps({k:v for k,v in result.items() if k not in ['validation','reset_checks','probes']}),flush=True);return result

    def real(s,ticks,delta=None):
        obs,info,h,xh,valid=prefix(s,ticks)
        # Resets during the measured trajectory may select another motion.
        # The differentiated trajectory must retain its STARTING command.
        initial=(obs.clone(),h.clone(),xh.clone(),env._motion_ids.clone(),env._perturbed_rows.clone())
        active=torch.ones(n,device=device,dtype=torch.bool);total=torch.zeros(n,device=device);trajectory=[]
        for t in range(horizon):
            obs,info,h,xh,d=step(obs,info,h,xh,delta if t==0 else None)
            total+=.99**t*active*d['reward'];active &= ~d['done'];trajectory.append(d)
        return initial,valid,total,trajectory

    for ticks in [8,40,70]:
        s=91871+ticks;(obs,h,xh,motion,pert),valid,control,trajectory=real(s,ticks)
        changed_motion=int((motion!=env._motion_ids).sum())
        loco=env._gaits[motion]!=-1
        delta=torch.zeros((n,34),device=device,requires_grad=True)
        x=ctx.physical(obs);phase=obs[:,-2:];alive=torch.ones(n,device=device);total=torch.zeros_like(alive)
        for t,d in enumerate(trajectory):
            raw,action,pred_phase=ctx.policy(x,motion,phase)
            if t==0:action=(raw+delta).clamp(ctx.low,ctx.high)
            clock=ctx.clock_phase(motion,d['times'])
            phase=anchor(torch.where(pert[:,None],F.normalize(pred_phase,dim=-1,eps=1e-6),clock),d['next_phase'])
            next_x=anchor(wm.step(x,action),d['next_x'])
            _,_,v,_=exact.bodies(x,xh[:,-1]);_,_,nv,_=exact.bodies(next_x,xh[:,-1])
            next_xy=anchor(xh[:,-1]+(v[:,0,:2]+nv[:,0,:2])*(1/60.),d['next_xy'])
            h=torch.cat((h[:,1:],next_x[:,None]),1);xh=torch.cat((xh[:,1:],next_xy[:,None]),1)
            reward,_=exact(h,xh,motion,phase,d['age'],d['times'],pert)
            # Actual discrete failure has no pathwise derivative. This audit
            # tests only the unchanged dense reward, with no critic contribution.
            total+=.99**t*alive*reward;alive=alive*(~d['done']);x=next_x
        gradient=torch.autograd.grad(total.sum(),delta)[0].detach()
        if not torch.isfinite(gradient).all():raise RuntimeError('Nonfinite exact reward gradient')
        direction=gradient/gradient.square().mean(-1,keepdim=True).sqrt().clamp_min(1e-8)
        for amplitude in [.01,.04]:
            positive=real(s,ticks,amplitude*direction);negative=real(s,ticks,-amplitude*direction)
            mismatch=torch.stack([(r[0][0]-obs).abs().amax(-1) for r in [positive,negative]]).amax(0)
            mask=valid&positive[1]&negative[1]&(mismatch<2e-4)&pert&loco
            change=(positive[2]-negative[2])[mask]
            predicted_change=(gradient*(2*amplitude*direction)).sum(-1)[mask]
            row=dict(prefix_ticks=ticks,amplitude=amplitude,rows=int(mask.sum()),
                post_rollout_motion_changes=changed_motion,
                real_reward_change=float(change.mean()),predicted_linear_change=float(predicted_change.mean()),
                positive_fraction=float((change>0).float().mean()),max_initial_mismatch=float(mismatch.max()),
                row_valid=mask.cpu().tolist(),row_real_delta=(positive[2]-negative[2]).cpu().tolist())
            result['probes'].append(row);base.write(out/'result.json',result)
            print('REWARD_AUDIT_GRADIENT',json.dumps({k:v for k,v in row.items() if not k.startswith('row_')}),flush=True)
    result.update(complete=True,passed=True,seconds=time.perf_counter()-started)
    base.write(out/'result.json',result);print('REWARD_AUDIT_COMPLETE',result['seconds'],flush=True)
    return result
