"""Bounded precision experiment on a disposable model; never updates policy."""
import copy
import json
import time
import torch

def benchmark(agent, directory):
    original_precision=torch.get_float32_matmul_precision()
    model=copy.deepcopy(agent._model)
    results={};references={}
    flat=agent._exp_buffer._flat_buffers
    try:
        for mode in ['highest','high','bfloat16']:
            torch.set_float32_matmul_precision('high' if mode=='high' else 'highest')
            for part,n in [('actor',16384),('critic',8192)]:
                obs=agent._obs_norm.normalize(flat['obs'][:n]).detach()
                action=agent._a_norm.normalize(flat['action'][:n]).detach()
                old_logp=flat['a_logp'][:n];adv=flat['adv'][:n];target=flat['tar_val'][:n]
                assert torch.all(flat['rand_action_mask'][:n]==1), 'Benchmark requires all exploratory actions'
                def compute():
                    model.zero_grad(set_to_none=True)
                    with torch.autocast('cuda',dtype=torch.bfloat16,enabled=mode=='bfloat16'):
                        if part=='actor':
                            dist=model.eval_actor(obs);prediction=dist.mode
                            ratio=torch.exp(dist.log_prob(action)-old_logp)
                            loss=-torch.minimum(adv*ratio,adv*ratio.clamp(1-agent._ppo_clip_ratio,1+agent._ppo_clip_ratio)).mean()
                        else:
                            prediction=model.eval_critic(obs).squeeze(-1)
                            loss=(target-prediction).square().mean()
                    loss.backward()
                    return prediction.detach().float(),loss.detach().float()
                for _ in range(3): compute()
                torch.cuda.synchronize();start=time.perf_counter()
                for _ in range(8): pred,loss=compute()
                torch.cuda.synchronize();seconds=(time.perf_counter()-start)/8
                grad=torch.cat([p.grad.flatten() for p in model.parameters() if p.grad is not None])
                if mode=='highest': references[part]=(pred.clone(),loss.clone(),grad.clone())
                rp,rl,rg=references[part]
                results[f'{mode}_{part}']=dict(batch=n,seconds=seconds,loss=loss.item(),
                    prediction_max_abs_error=(pred-rp).abs().max().item(),
                    loss_abs_error=(loss-rl).abs().item(),
                    gradient_relative_l2=((grad-rg).norm()/rg.norm().clamp_min(1e-10)).item(),
                    gradients_finite=bool(torch.isfinite(grad).all()))
    finally:
        torch.set_float32_matmul_precision(original_precision)
        del model
    (directory/'precision_benchmark.json').write_text(json.dumps(results,indent=2))
