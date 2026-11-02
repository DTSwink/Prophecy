"""Isolated frozen-policy physics cost/fidelity screen; no training or deployment."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
import torch
import supermimic_race as base


def run(root,checkpoint,output,method):
    started=time.perf_counter();root=Path(root).resolve();output=Path(output).resolve();output.mkdir(exist_ok=True)
    sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')];os.chdir(root/'MimicKit')
    os.environ['PYGLET_HEADLESS']='true';torch.set_num_threads(2)
    import warp as wp,yaml
    from util import mp_util
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from resume import restore,migrate_physical_observation_scales
    import native_uefn_engine
    original=native_uefn_engine.configure_native_model
    audit={}
    def configure(model,metadata):
        result=original(model,metadata)
        audit['original']=dict(iterations=int(model.opt.iterations),ls_iterations=int(model.opt.ls_iterations),tolerance=float(model.opt.tolerance))
        if method=='cap4':model.opt.iterations=4;model.opt.ls_iterations=4
        elif method!='original':raise ValueError(method)
        assert abs(model.opt.timestep-1/240)<1e-12
        audit['actual']=dict(iterations=int(model.opt.iterations),ls_iterations=int(model.opt.ls_iterations),tolerance=float(model.opt.tolerance),physics_hz=240,policy_hz=30)
        return result
    native_uefn_engine.configure_native_model=configure
    wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6895);base.seed(849210)
    cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
    env=PerturbedOmniEnv(cfg,ec,1024,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
    restore(agent,checkpoint)
    if cfg['perturbed_motion'].get('observation_normalization')=='physical_scales_v1':migrate_physical_observation_scales(agent)
    agent._init_train();agent.eval();initial={k:v.detach().clone() for k,v in agent.state_dict().items()}
    gpu_options=env._engine._solver.mjw_model.opt
    assert gpu_options.iterations==audit['actual']['iterations'] and gpu_options.ls_iterations==audit['actual']['ls_iterations']
    report=dict(kind='native_fidelity_screen',complete=False,method=method,actor_updates=0,options=audit,
        checkpoint_sha256=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),evaluations=[],
        setup_seconds=time.perf_counter()-started,scope='Only Newton and line-search iteration caps differ. Same frequency, geometry, friction, limits, motors, rewards, policy and noise. No training.')
    print('NATIVE_FIDELITY_READY',json.dumps(report),flush=True)
    warm=time.perf_counter();base.evaluate(env,agent,[849210],max_ticks=120,exploration=True)
    torch.cuda.synchronize();report['warmup_seconds']=time.perf_counter()-warm
    # Separate seeds/modes and warmed GPU timing; original native simulator
    # remains the evaluation standard for any later learning experiment.
    for seed in [984210,984211]:
        for noisy in [False,True]:
            torch.cuda.synchronize();clock=time.perf_counter()
            rows=base.evaluate(env,agent,[seed],max_ticks=300,exploration=noisy)
            torch.cuda.synchronize();elapsed=time.perf_counter()-clock
            item=dict(seed=seed,exploration=noisy,seconds=elapsed,rows=rows)
            report['evaluations'].append(item);base.write(output/'result.json',report)
            print('NATIVE_FIDELITY_EVAL',json.dumps(dict(seed=seed,noisy=noisy,seconds=elapsed,groups=rows[0]['groups'])),flush=True)
    report['policy_max_abs_delta']=max(float((v-initial[k]).abs().max()) for k,v in agent.state_dict().items())
    assert report['policy_max_abs_delta']==0
    report.update(complete=True,total_worker_seconds=time.perf_counter()-started)
    base.write(output/'result.json',report);print('NATIVE_FIDELITY_COMPLETE',method,report['total_worker_seconds'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ['root','checkpoint','output','method']:p.add_argument('--'+k,required=True)
    run(**vars(p.parse_args()))
