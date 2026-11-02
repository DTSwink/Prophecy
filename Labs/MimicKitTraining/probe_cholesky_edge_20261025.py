"""Native-block edge specialization: exact live-vector gate before timing."""
import json,os,signal,subprocess,sys,time,traceback,statistics
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-lossless-20261024/cholesky-edge';OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')];os.chdir(ROOT)
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
from lossless_runtime import install
from cholesky_edge_probe import CholeskyEdge

def guarded_times(a,run,graphs,sequence,label):
    pid=json.loads((ROOT/(run.name+'-launch.json')).read_text())['pid']
    cmd=(Path('/proc')/str(pid)/'cmdline').read_bytes()
    assert run.name.encode() in cmd and b'pipeline/train.py' in cmd
    status=json.loads((run/'status.json').read_text());backup=json.loads((run/'backup_status.json').read_text())
    assert status['state']=='training' and time.time()-status['updated_unix']<180
    assert time.time()-backup['verified_unix']<600
    code="import os,signal,time;from pathlib import Path;time.sleep(60);p=Path('/proc')/"+repr(str(pid))+"/'cmdline'\nif p.exists() and "+repr(run.name.encode())+" in p.read_bytes():os.kill("+str(pid)+",signal.SIGCONT)"
    guard=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    paused=False;start=time.time();rows=[]
    try:
        os.kill(pid,signal.SIGSTOP);paused=True
        (OUT/(label+'-pause.json')).write_text(json.dumps(dict(pid=pid,guard=guard.pid,start=start)))
        time.sleep(.3)
        for name in sequence:
            a._env._engine._graph=graphs[name]
            torch.cuda.synchronize();t=time.perf_counter();a._train_iter();torch.cuda.synchronize()
            rows.append(dict(variant=name,seconds=time.perf_counter()-t))
            print(json.dumps(rows[-1]),flush=True)
            assert time.time()-start<50
    finally:
        if paused:os.kill(pid,signal.SIGCONT)
        guard.terminate();guard.wait(timeout=5)
        (OUT/(label+'-resumed.json')).write_text(json.dumps(dict(pid=pid,resumed=time.time(),seconds=time.time()-start)))
    return rows


def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6844)
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    e=PerturbedOmniEnv(cfg,ec,2048,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    run=ROOT/'runs'/sys.argv[1];cp=json.loads((run/'backup_status.json').read_text())
    restore(a,run/Path(cp['key']).name);a._init_train();a.set_mode(AgentMode.TRAIN)
    a._curr_obs,a._curr_info=a._reset_envs();install(a,e)
    for _ in range(2):a._train_iter()
    eng=e._engine;m=eng._solver.mjw_model;d=eng._solver.mjw_data
    sparse,factor=eng._dispatch_resources;early=eng._converged_newton_resource
    graphs={'current':eng._graph};candidate=CholeskyEdge(m,d);candidate.audit=True
    before=dict(sparse.hits);f_before=factor.hits
    with sparse.capture(),factor.capture(),early.capture(),candidate.capture():eng._build_graphs()
    assert {k:sparse.hits[k]-before[k] for k in before}=={'velocity':8,'derivative':8}
    assert factor.hits-f_before==16
    assert candidate.hits==16,candidate.hits
    with torch.no_grad():
        for tick in range(24):
            action,_=a._decide_action(a._curr_obs,a._curr_info)
            obs,reward,done,info=a._step_env(action)
            a._curr_obs,a._curr_info=a._reset_done_envs(done)
            if tick%4==3:
                check=dict(ticks=tick+1,counts=candidate.counts.numpy().sum(0).tolist(),max_abs=float(candidate.maximum.numpy().max()))
                (OUT/'parity.json').write_text(json.dumps(check,indent=2));print(json.dumps(check),flush=True)
                if check['counts'][1] or check['counts'][2]:
                    (OUT/'complete.json').write_text(json.dumps(dict(disposition='Rejected: changed native factorization outputs',parity=check),indent=2));return
    candidate.audit=False
    before=dict(sparse.hits);f_before=factor.hits
    with sparse.capture(),factor.capture(),early.capture(),candidate.capture():eng._build_graphs()
    assert {k:sparse.hits[k]-before[k] for k in before}=={'velocity':8,'derivative':8}
    assert factor.hits-f_before==16
    graphs['edge40']=eng._graph
    for g in graphs.values():eng._graph=g;a._train_iter()
    rows=guarded_times(a,run,graphs,['current','edge40','edge40','current']*3,'comparison')
    means={n:statistics.mean(x['seconds'] for x in rows if x['variant']==n) for n in graphs}
    (OUT/'complete.json').write_text(json.dumps(dict(checkpoint=cp,parity=check,measurements=rows,means=means,disposition='Measured; not deployed'),indent=2))

if __name__=='__main__':
    try:main()
    except Exception:
        (OUT/'failure.txt').write_text(traceback.format_exc());raise
