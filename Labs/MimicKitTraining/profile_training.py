"""Opt-in, three-update audit. Removed completely after the measured updates."""
import json
import time
from collections import defaultdict
import torch


def run_profiled_update(agent, update, directory, index):
    rows=defaultdict(lambda: dict(calls=0, cpu_seconds=0., cuda_ms=0.))
    events=[];originals=[]
    def wrap(obj, name, label, synchronize=False):
        original=getattr(obj,name)
        originals.append((obj,name,original))
        def measured(*args,**kwargs):
            if synchronize: torch.cuda.synchronize()
            start=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
            start.record();begun=time.perf_counter()
            with torch.profiler.record_function(label):
                result=original(*args,**kwargs)
            end.record()
            if synchronize: torch.cuda.synchronize()
            rows[label]['calls']+=1;rows[label]['cpu_seconds']+=time.perf_counter()-begun
            events.append((label,start,end))
            return result
        setattr(obj,name,measured)
    for method in ['_rollout_train','_build_train_data','_update_actor','_update_critic','_update_normalizers']:
        wrap(agent,method,method,True)
    for method in ['_decide_action','_reset_done_envs','_record_data_pre_step','_record_data_post_step']:
        wrap(agent,method,method)
    wrap(agent._env._engine,'step','physics_step')
    wrap(agent._env._engine,'_update_contact_sensors','contact_sensors')
    wrap(agent._env,'_post_physics_step','observations_reward_done')
    wrap(agent._exp_buffer,'sample','minibatch_gathers')
    try:
        torch.cuda.synchronize();begun=time.perf_counter()
        if index==2:
            with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,torch.profiler.ProfilerActivity.CUDA]) as profiler:
                result=update()
            table=profiler.key_averages()
            (directory/'profile_ops.txt').write_text(table.table(sort_by='self_cuda_time_total',row_limit=45))
            ops=[dict(name=x.key,calls=x.count,cpu_us=x.self_cpu_time_total,cuda_us=x.self_device_time_total) for x in table]
            (directory/'profile_ops.json').write_text(json.dumps(ops))
        else:
            result=update()
        torch.cuda.synchronize()
        elapsed=time.perf_counter()-begun
        for label,start,end in events: rows[label]['cuda_ms']+=start.elapsed_time(end)
        report=dict(index=index,elapsed_seconds=elapsed,ranges=dict(rows),
                    note='Nested ranges overlap. Coarse phases synchronize for attribution; detailed CUDA events use the PyTorch stream. Profiling overhead is not normal training time.',
                    precision=torch.get_float32_matmul_precision(),tf32_matmul=torch.backends.cuda.matmul.allow_tf32,
                    mixed_precision=agent._use_mixed_precision,peak_allocated_bytes=torch.cuda.max_memory_allocated())
        (directory/f'profile_{index}.json').write_text(json.dumps(report,indent=2))
        if index==2:
            from benchmark_precision import benchmark
            benchmark(agent,directory)
        return result
    finally:
        for obj,name,original in reversed(originals): setattr(obj,name,original)
