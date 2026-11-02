"""Bounded, isolated profiler for the current 2048-world locomotion workload."""
import sys,json,time,os,cProfile,pstats,io,traceback
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
OUT=ROOT/'perf-lossless-20261024';OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
os.chdir(ROOT)
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from resume import restore
from omni_policy import OmniPPOAgent
from profile_training import run_profiled_update

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6817)
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    begun=time.time();env=PerturbedOmniEnv(cfg,ec,2048,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
    run=ROOT/'runs'/sys.argv[1];b=json.loads((run/'backup_status.json').read_text());restore(agent,run/Path(b['key']).name)
    agent._init_train();agent.set_mode(AgentMode.TRAIN);agent._curr_obs,agent._curr_info=agent._reset_envs()
    measurements=[]
    for i in range(3):
        agent._iter=i;torch.cuda.synchronize();start=time.perf_counter();agent._train_iter();torch.cuda.synchronize()
        measurements.append(time.perf_counter()-start)
    prof=cProfile.Profile();prof.enable();run_profiled_update(agent,agent._train_iter,OUT,0);prof.disable()
    stream=io.StringIO();pstats.Stats(prof,stream=stream).sort_stats('cumtime').print_stats(100);(OUT/'python_calls.txt').write_text(stream.getvalue())
    prof.dump_stats(str(OUT/'python_calls.prof'))
    with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,torch.profiler.ProfilerActivity.CUDA]) as trace:
        agent._train_iter();torch.cuda.synchronize()
    table=trace.key_averages()
    (OUT/'operators.txt').write_text(table.table(sort_by='self_cuda_time_total',row_limit=80))
    ops=[dict(name=x.key,calls=x.count,cpu_us=x.self_cpu_time_total,cuda_us=x.self_device_time_total) for x in table]
    (OUT/'operators.json').write_text(json.dumps(ops))
    trace.export_chrome_trace(str(OUT/'trace.json.gz'))
    result=dict(checkpoint=b,worlds=2048,warm_updates_seconds=measurements,total_seconds=time.time()-begun,
        peak_memory=torch.cuda.max_memory_allocated(),note='Concurrent with production; attribution only, not isolated throughput')
    (OUT/'complete.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
    try:main()
    except Exception:
        (OUT/'failure.txt').write_text(traceback.format_exc());raise
