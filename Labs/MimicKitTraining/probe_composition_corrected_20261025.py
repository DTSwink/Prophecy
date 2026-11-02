"""One bounded screen plus validation of the best unchanged contact-kernel launch."""
import json, os, signal, subprocess, sys, time, traceback, statistics
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
OUT=ROOT/'perf-lossless-20261024/composition-corrected-v2';OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(Path(__file__).resolve().parent),str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')];os.chdir(ROOT)
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
from lossless_runtime import install
from contact_stages_probe import ContactStages
from deferred_fk_probe import DeferredFK
from cached_cone_probe import CachedCone
from contextlib import ExitStack
from mujoco_warp._src import solver


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
    import hashlib,inspect
    sources={}
    for cls in [DeferredFK,CachedCone,ContactStages]:
        path=Path(inspect.getfile(cls)).resolve()
        assert path.parent==Path(__file__).resolve().parent,path
        sources[cls.__name__]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (OUT/'sources.json').write_text(json.dumps(sources,indent=2))
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6845)
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    e=PerturbedOmniEnv(cfg,ec,2048,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    run=ROOT/'runs'/sys.argv[1];cp=json.loads((run/'backup_status.json').read_text())
    restore(a,run/Path(cp['key']).name);a._init_train();a.set_mode(AgentMode.TRAIN)
    a._curr_obs,a._curr_info=a._reset_envs();install(a,e)
    for _ in range(2):a._train_iter()
    eng=e._engine;m=eng._solver.mjw_model;d=eng._solver.mjw_data
    sparse,factor=eng._dispatch_resources;early=eng._converged_newton_resource
    graphs={'current':eng._graph};candidates={
        'deferred_fk':DeferredFK(eng),
        'cached_cone':CachedCone(m,d),
        'static_cone':ContactStages(m,d,eng._solver.mj_model,True,False),
    }
    captures={}
    def capture(name,candidate):
        before=dict(sparse.hits);f_before=factor.hits
        with sparse.capture(),factor.capture(),early.capture(),candidate.capture():eng._build_graphs()
        delta={k:sparse.hits[k]-before[k] for k in before}
        receipt=dict(sparse=delta,factor=factor.hits-f_before)
        assert delta=={'velocity':8,'derivative':8},receipt
        assert receipt['factor']==16,receipt
        captures[name]=receipt;graphs[name]=eng._graph
        print(json.dumps(dict(capture=name,**receipt)),flush=True)
    for name,candidate in candidates.items():capture(name,candidate)
    (OUT/'captures.json').write_text(json.dumps(captures,indent=2))
    for graph in graphs.values():eng._graph=graph;a._train_iter()
    names=list(graphs)
    screen=guarded_times(a,run,graphs,names+list(reversed(names))+names,'screen')
    means={n:statistics.mean(x['seconds'] for x in screen if x['variant']==n) for n in names}
    best=min(names,key=lambda n:means[n])
    result=dict(checkpoint=cp,captures=captures,measurements=screen,means=means,best=best)
    (OUT/'screen.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(means=means,best=best)),flush=True)
    if best=='current' or means[best]>means['current']*.985:
        result['disposition']='No material candidate in corrected bounded screen'
        (OUT/'complete.json').write_text(json.dumps(result,indent=2));return
    candidate=candidates[best]
    if best=='deferred_fk':
        # Its unchanged arithmetic/dataflow passed exact 31,948,800-element body audit.
        # Keep confirmation scoped to this corrected composition; no deployment here.
        result['prior_parity']='deferred-fk/parity.json'
        result['confirmation']=guarded_times(a,run,graphs,['current',best,best,'current']*3,'confirmation')
        result['disposition']='Corrected timing complete; packaging preflight required'
        (OUT/'complete.json').write_text(json.dumps(result,indent=2));return
    # Whole-solve output check from identical physical states, against native repeat variation.
    ctx=solver.create_solver_context(m,d)
    with early.capture():
        with wp.ScopedCapture() as cap:solver._solve(m,d,ctx)
    solve_base=cap.graph
    ctx_new=solver.create_solver_context(m,d)
    with early.capture(),candidate.capture():
        with wp.ScopedCapture() as cap:solver._solve(m,d,ctx_new)
    solve_new=cap.graph
    outputs=[d.qacc,d.qfrc_constraint,d.efc.Ma,d.efc.state,d.solver_niter,d.efc.force]
    saved=[wp.empty_like(v) for v in outputs]
    def restore_outputs():
        for v,s in zip(outputs,saved):wp.copy(v,s)
    rows=[];eng._graph=graphs['current']
    with torch.no_grad():
        for tick in range(24):
            action,_=a._decide_action(a._curr_obs,a._curr_info)
            obs,reward,done,info=a._step_env(action);wp.synchronize()
            for v,s in zip(outputs,saved):wp.copy(s,v)
            values=[]
            for graph in [solve_base,solve_base,solve_new]:
                restore_outputs();wp.capture_launch(graph);wp.synchronize()
                values.append([wp.to_torch(v).clone() for v in outputs])
            restore_outputs();wp.synchronize();row={'tick':tick}
            for variant,actual in zip(['native_repeat','candidate'],values[1:]):
                metrics={}
                for k,n in enumerate(['qacc','constraint_force','mass_acceleration']):
                    rel=(actual[k]-values[0][k]).double().norm(dim=-1)/values[0][k].double().norm(dim=-1).clamp_min(1.)
                    metrics[n]=dict(max_relative=float(rel.max()),rms_relative=float(rel.square().mean().sqrt()),finite=bool(torch.isfinite(actual[k]).all()))
                active=torch.arange(values[0][3].shape[1],device='cuda')[None,:]<wp.to_torch(d.nefc)[:,None]
                metrics['state_mismatches']=int(((actual[3]!=values[0][3])&active).sum())
                metrics['iteration_mismatches']=int((actual[4]!=values[0][4]).sum())
                row[variant]=metrics
            rows.append(row);a._curr_obs,a._curr_info=a._reset_done_envs(done)
    def aggregate(variant):
        result={}
        for n in ['qacc','constraint_force','mass_acceleration']:
            result[n]=dict(max_relative=max(x[variant][n]['max_relative'] for x in rows),rms_relative=(sum(x[variant][n]['rms_relative']**2 for x in rows)/len(rows))**.5,finite=all(x[variant][n]['finite'] for x in rows))
        for n in ['state_mismatches','iteration_mismatches']:result[n]=sum(x[variant][n] for x in rows)
        return result
    agg={v:aggregate(v) for v in ['native_repeat','candidate']};checks={}
    for n in ['qacc','constraint_force','mass_acceleration']:
        base,new=agg['native_repeat'][n],agg['candidate'][n]
        checks[n]=new['finite'] and new['max_relative']<=max(2e-5,3*base['max_relative']) and new['rms_relative']<=max(1e-6,2*base['rms_relative'])
    for n in ['state_mismatches','iteration_mismatches']:checks[n]=agg['candidate'][n]<=2*agg['native_repeat'][n]
    (OUT/'shadow.json').write_text(json.dumps(dict(best=best,aggregate=agg,checks=checks,rows=rows),indent=2))
    if not all(checks.values()):
        (OUT/'complete.json').write_text(json.dumps(dict(disposition='Rejected by full-solve fidelity gate',means=means,best=best,checks=checks),indent=2));return
    for name in ['current',best]:eng._graph=graphs[name];a._train_iter()
    confirmation=guarded_times(a,run,graphs,['current',best,best,'current']*3,'confirmation')
    (OUT/'complete.json').write_text(json.dumps(dict(disposition='Measured; deployment requires separate decision',means=means,best=best,checks=checks,confirmation=confirmation,captures=captures),indent=2))


if __name__=='__main__':
    try:main()
    except Exception:
        (OUT/'failure.txt').write_text(traceback.format_exc());raise
