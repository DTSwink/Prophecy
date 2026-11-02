"""Audit candidate kernels beside originals on live-policy states; originals drive physics."""
import json,os,sys,traceback
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
from fused_factor_probe import FusedFactor
from mujoco_warp._src import smooth

@wp.kernel(enable_backward=False)
def compare_exact(a:wp.array2d(dtype=float),b:wp.array2d(dtype=float),index:int,counts:wp.array(dtype=int)):
    i,j=wp.tid();x=a[i,j];y=b[i,j]
    if not wp.isfinite(x):wp.atomic_add(counts,2,1)
    if x!=y and not (wp.isnan(x) and wp.isnan(y)):wp.atomic_add(counts,index,1)

@wp.kernel(enable_backward=False)
def compare_factor(a:wp.array2d(dtype=float),b:wp.array2d(dtype=float),index:int,error:wp.array(dtype=float)):
    i,j=wp.tid();x=a[i,j];y=b[i,j]
    wp.atomic_max(error,index,wp.abs(x-y))

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6825)
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    e=PerturbedOmniEnv(cfg,ec,128,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    run=ROOT/'runs'/sys.argv[1];b=json.loads((run/'backup_status.json').read_text());restore(a,run/Path(b['key']).name)
    a._init_train();a.set_mode(AgentMode.TRAIN);a._curr_obs,a._curr_info=a._reset_envs()
    eng=e._engine;s=eng._solver;m=s.mjw_model;d=s.mjw_data
    sp=SparseActuators(s.mj_model,m,d);f=FusedFactor(m,d)
    v=wp.zeros_like(d.actuator_velocity);y=wp.zeros_like(d.qM)
    l=wp.zeros_like(d.qLD);diag=wp.zeros_like(d.qLDiagInv);repeat=wp.zeros_like(l);repeat_diag=wp.zeros_like(diag)
    counts=wp.zeros(3,dtype=int);error=wp.zeros(4,dtype=float)
    sp.velocity(v);sp.deriv(v,y);f.apply(m,d,d.qM,l,diag)
    wp.launch(compare_exact,dim=v.shape,inputs=[v,v,0,counts]);wp.launch(compare_factor,dim=diag.shape,inputs=[diag,diag,0,error])
    launch,tiled,original_factor=wp.launch,wp.launch_tiled,smooth._factor_i_sparse
    hits={'velocity':0,'derivative':0,'factor':0}
    def audit_launch(kernel,*args,**kw):
        result=launch(kernel,*args,**kw);inputs=kw.get('inputs',[])
        if kernel is sp.old_derivative and len(inputs)==5 and inputs[1] is d.actuator_moment:
            hits['derivative']+=1;sp.deriv(inputs[2],y)
            old=kw['outputs'][0]
            launch(compare_exact,dim=(d.nworld,y.shape[2]),inputs=[old.reshape((d.nworld,y.shape[2])),y.reshape((d.nworld,y.shape[2])),1,counts])
        return result
    def audit_tiled(kernel,*args,**kw):
        result=tiled(kernel,*args,**kw);inputs=kw.get('inputs',[])
        if kernel is sp.old_velocity and len(inputs)==2 and inputs[0] is d.qvel:
            hits['velocity']+=1;sp.velocity(v)
            launch(compare_exact,dim=v.shape,inputs=[kw['outputs'][0],v,0,counts])
        return result
    def audit_factor(mm,dd,M,L,D):
        result=original_factor(mm,dd,M,L,D)
        if mm is m and dd is d:
            hits['factor']+=1;assert M.ptr!=L.ptr
            f.apply(m,d,M,l,diag);original_factor(m,d,M,repeat,repeat_diag)
            shape=(d.nworld,L.shape[2])
            launch(compare_factor,dim=shape,inputs=[L.reshape(shape),l.reshape(shape),0,error])
            launch(compare_factor,dim=shape,inputs=[L.reshape(shape),repeat.reshape(shape),1,error])
            launch(compare_factor,dim=D.shape,inputs=[D,diag,2,error]);launch(compare_factor,dim=D.shape,inputs=[D,repeat_diag,3,error])
        return result
    try:
        wp.launch=audit_launch;wp.launch_tiled=audit_tiled;smooth._factor_i_sparse=audit_factor
        eng._build_graphs()
    finally:wp.launch=launch;wp.launch_tiled=tiled;smooth._factor_i_sparse=original_factor
    assert hits==dict(velocity=8,derivative=8,factor=16),hits
    done_counts=torch.zeros(4,device='cuda',dtype=torch.int64)
    with torch.no_grad():
        for tick in range(300):
            action,_=a._decide_action(a._curr_obs,a._curr_info)
            obs,reward,done,info=a._step_env(action)
            for flag in range(4):done_counts[flag]+=(done==flag).sum()
            a._curr_obs,a._curr_info=a._reset_done_envs(done)
            if tick%50==49:
                wp.synchronize();result=dict(ticks=tick+1,worlds=128,physics_states=128*8*(tick+1),mismatch_counts=counts.numpy().tolist(),factor_errors=error.numpy().tolist(),done_counts=done_counts.cpu().tolist(),intercepts=hits)
                (OUT/'physics-shadow-progress.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
                assert result['mismatch_counts']==[0,0,0],result
    (OUT/'physics-shadow-complete.json').write_text(json.dumps(result,indent=2))

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'physics-shadow-failure.txt').write_text(traceback.format_exc());raise
