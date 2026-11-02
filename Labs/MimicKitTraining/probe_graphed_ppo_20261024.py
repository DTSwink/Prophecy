"""Current-workload exact update parity and bounded PPO dispatch A/B."""
import json,os,signal,subprocess,sys,time,traceback,copy
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-lossless-20261024'
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')];os.chdir(ROOT)
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from resume import restore
from omni_policy import OmniPPOAgent
from kl_guard import Snapshot
from graphed_ppo_probe import GraphedLoss

def compare(a,b):
    if isinstance(a,torch.Tensor):return dict(equal=torch.equal(a,b),max_error=float((a-b).abs().max()) if a.numel() else 0.)
    if isinstance(a,dict):return {str(k):compare(v,b[k]) for k,v in a.items()}
    if isinstance(a,(list,tuple)):return [compare(v,w) for v,w in zip(a,b)]
    return dict(equal=a==b,max_error=0 if a==b else 1)
def all_equal(x):
    if isinstance(x,dict):return x['equal'] if 'equal' in x else all(all_equal(v) for v in x.values())
    return all(all_equal(v) for v in x)

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6824)
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    e=PerturbedOmniEnv(cfg,ec,2048,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    run=ROOT/'runs'/sys.argv[1];b=json.loads((run/'backup_status.json').read_text());restore(a,run/Path(b['key']).name)
    a._init_train();a.set_mode(AgentMode.TRAIN);a._curr_obs,a._curr_info=a._reset_envs()
    for _ in range(2):a._train_iter()
    graphs={};originals={};checks={}
    for kind,size in [('actor',8192),('critic',4096)]:
        name='_compute_'+kind+'_loss';fn=getattr(a,name);o=getattr(a,'_'+kind+'_optimizer');batch=a._exp_buffer.sample(size)
        g=GraphedLoss(fn,o,batch,kind+'_loss');graphs[kind]=g;originals[kind]=fn
        snap=Snapshot(o);info=fn(batch);expected_info={k:v.detach().clone() for k,v in info.items()};o.step(info[kind+'_loss'])
        expected=[p.detach().clone() for p in o._param_list];expected_state=copy.deepcopy(o._optimizer.state_dict())
        snap.restore();got=g(batch);actual_info={k:v.detach().clone() for k,v in got.items()};g.step(got[kind+'_loss']);torch.cuda.synchronize()
        check=dict(losses=compare(expected_info,actual_info),parameters=compare(expected,[p.detach() for p in o._param_list]),optimizer=compare(expected_state,o._optimizer.state_dict()))
        checks[kind]=check;(OUT/'ppo-graph-parity.json').write_text(json.dumps(checks,indent=2))
        assert all_equal(check),kind+' graph changed update'
        snap.restore()
    def select(mode):
        for kind,g in graphs.items():
            setattr(a,'_compute_'+kind+'_loss',g if mode else originals[kind])
            g.install() if mode else g.uninstall()
    select(True)
    for _ in range(2):a._train_iter()
    torch.cuda.synchronize();mainpid=2180;cmd=(Path('/proc')/str(mainpid)/'cmdline').read_bytes()
    assert sys.argv[1].encode() in cmd and b'pipeline/train.py' in cmd
    status=json.loads((run/'status.json').read_text());assert status['state']=='training' and time.time()-status['updated_unix']<180
    backup=json.loads((run/'backup_status.json').read_text());assert time.time()-backup['verified_unix']<600
    code="import os,signal,time;from pathlib import Path;time.sleep(60);p=Path('/proc/2180/cmdline');"+f"\nif p.exists() and {sys.argv[1]!r}.encode() in p.read_bytes():os.kill(2180,signal.SIGCONT)"
    guard=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    start=time.time();rows=[];paused=False
    try:
        os.kill(mainpid,signal.SIGSTOP);paused=True
        (OUT/'ppo-graph-pause.json').write_text(json.dumps(dict(start=start,pid=mainpid,guard=guard.pid,maximum_seconds=60)))
        time.sleep(.3)
        for mode in [False,True,True,False]*2:
            select(mode);torch.cuda.synchronize();t=time.perf_counter();a._train_iter();torch.cuda.synchronize()
            rows.append(dict(optimized=mode,seconds=time.perf_counter()-t));print(json.dumps(rows[-1]),flush=True)
            assert time.time()-start<50
    finally:
        if paused:os.kill(mainpid,signal.SIGCONT)
        guard.terminate();guard.wait(timeout=5)
        (OUT/'ppo-graph-resumed.json').write_text(json.dumps(dict(pid=mainpid,resumed=time.time(),pause_seconds=time.time()-start)))
    result=dict(checkpoint=b,all_update_checks_exact=True,measurements=rows)
    (OUT/'ppo-graph-complete.json').write_text(json.dumps(result,indent=2));print('RESULT'+json.dumps(result),flush=True)

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'ppo-graph-failure.txt').write_text(traceback.format_exc());raise
