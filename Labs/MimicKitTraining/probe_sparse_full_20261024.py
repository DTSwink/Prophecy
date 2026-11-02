"""Disposable full-engine parity and guarded full-update timing."""
import json,os,signal,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-lossless-20261024'
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')];os.chdir(ROOT)
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from resume import restore
from omni_policy import OmniPPOAgent
from sparse_actuator_probe import SparseActuators

def snapshot_engine(engine):
    arrays={};seen=set()
    def visit(x,depth=0):
        if x is None or id(x) in seen:return
        seen.add(id(x))
        if isinstance(x,wp.array):
            if x.ptr and x.size:arrays[('warp',x.ptr)]=x
        elif isinstance(x,torch.Tensor):
            if x.numel():arrays[('torch',x.data_ptr())]=x
        elif isinstance(x,(list,tuple)):
            for item in x:visit(item,depth+1)
        elif isinstance(x,dict):
            for item in x.values():visit(item,depth+1)
        elif depth<4 and hasattr(x,'__dict__'):
            for name,item in vars(x).items():
                if 'model' not in name and 'engine' not in name:visit(item,depth+1)
    for root in [engine._solver.mjw_data,engine._sim_state,engine._state_swap_buffer,engine._controls]:visit(root)
    for item in vars(engine).values():
        if isinstance(item,(torch.Tensor,wp.array)):visit(item)
    saved=[(x,wp.clone(x) if isinstance(x,wp.array) else x.clone()) for x in arrays.values()]
    def reset():
        for x,y in saved:
            if isinstance(x,wp.array):wp.copy(x,y)
            else:x.copy_(y)
    return reset,len(saved)

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6823)
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    e=PerturbedOmniEnv(cfg,ec,2048,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    run=ROOT/'runs'/sys.argv[1];b=json.loads((run/'backup_status.json').read_text());restore(a,run/Path(b['key']).name)
    a._init_train();a.set_mode(AgentMode.TRAIN);a._curr_obs,a._curr_info=a._reset_envs()
    for _ in range(2):a._train_iter()
    eng=e._engine;s=eng._solver;sp=SparseActuators(s.mj_model,s.mjw_model,s.mjw_data)
    original=eng._graph
    # Compile the replacements before graph capture.
    sp.velocity(wp.zeros_like(s.mjw_data.actuator_velocity))
    sp.deriv(wp.zeros_like(s.mjw_data.actuator_velocity),wp.zeros_like(s.mjw_data.qM))
    with sp.capture():eng._build_graphs()
    optimized=eng._graph;assert sp.hits['velocity']==eng._sim_steps and sp.hits['derivative']==eng._sim_steps,sp.hits
    checks=[]
    for trial in range(3):
        eng._graph=original;a._train_iter()
        reset,count=snapshot_engine(eng)
        outputs=[]
        for graph in [original,original,optimized]:
            reset();wp.capture_launch(graph);wp.synchronize()
            outputs.append({k:wp.to_torch(getattr(s.mjw_data,k)).clone() for k in ['qpos','qvel','actuator_force','qacc']})
        row={'trial':trial,'snapshot_arrays':count}
        for k in outputs[0]:
            left,repeat,candidate=[o[k] for o in outputs]
            error=float((left-candidate).abs().max());variation=float((left-repeat).abs().max())
            row[k]=dict(max_error=error,reference_repeat_variation=variation)
            assert torch.isfinite(candidate).all(),row
            # Native atomic reductions vary between identical calls; record the floor.
            row[k]['strict_close']=bool(torch.allclose(candidate,left,atol=max(2e-4,variation*3),rtol=2e-4))
        checks.append(row);(OUT/'sparse-full-parity.json').write_text(json.dumps(checks,indent=2))
        reset();del reset,outputs
    eng._graph=optimized
    for _ in range(2):a._train_iter()
    torch.cuda.synchronize()
    mainpid=2180;p=Path('/proc')/str(mainpid)/'cmdline'
    assert sys.argv[1].encode() in p.read_bytes() and b'pipeline/train.py' in p.read_bytes()
    status=json.loads((run/'status.json').read_text());assert status['state']=='training' and time.time()-status['updated_unix']<180
    backup=json.loads((run/'backup_status.json').read_text());assert time.time()-backup['verified_unix']<600
    code="import os,signal,time;from pathlib import Path;time.sleep(60);p=Path('/proc/2180/cmdline');"+f"\nif p.exists() and {sys.argv[1]!r}.encode() in p.read_bytes():os.kill(2180,signal.SIGCONT)"
    guard=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    start=time.time();rows=[];paused=False
    try:
        os.kill(mainpid,signal.SIGSTOP);paused=True
        (OUT/'sparse-pause.json').write_text(json.dumps(dict(start=start,pid=mainpid,guard=guard.pid,maximum_seconds=60)))
        time.sleep(.3)
        for mode in [False,True,True,False]*2:
            eng._graph=optimized if mode else original
            torch.cuda.synchronize();t=time.perf_counter();a._train_iter();torch.cuda.synchronize()
            rows.append(dict(optimized=mode,seconds=time.perf_counter()-t));print(json.dumps(rows[-1]),flush=True)
            assert time.time()-start<50
    finally:
        if paused:os.kill(mainpid,signal.SIGCONT)
        guard.terminate();guard.wait(timeout=5)
        (OUT/'sparse-resumed.json').write_text(json.dumps(dict(pid=mainpid,resumed=time.time(),pause_seconds=time.time()-start)))
    result=dict(checkpoint=b,checks=checks,kernel_intercepts=sp.hits,measurements=rows)
    (OUT/'sparse-full-complete.json').write_text(json.dumps(result,indent=2));print('RESULT'+json.dumps(result),flush=True)

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'sparse-full-failure.txt').write_text(traceback.format_exc());raise
