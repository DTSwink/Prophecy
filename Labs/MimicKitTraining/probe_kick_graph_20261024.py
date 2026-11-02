"""Bounded, isolated dispatch experiment. Never writes production files."""
import json, os, sys, time, traceback
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-lossless-20261024'
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')];os.chdir(ROOT)
import torch, warp as wp, mujoco_warp as mjw, yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from resume import restore
from omni_policy import OmniPPOAgent
from final_locomotion import ArticulatedKicks
import final_locomotion

class GraphKicks(ArticulatedKicks):
    def __init__(self, engine):
        super().__init__(engine)
        self.graph=None
        nv=engine._solver.mj_model.nv
        self.points=[torch.empty((self.n,3),device=self.dev) for _ in self.ids]
        self.points_wp=[wp.from_torch(p,dtype=wp.vec3) for p in self.points]
        self.jacs=torch.empty((self.n,10,nv),device=self.dev)
        self.inverses=torch.empty((self.n,nv,10),device=self.dev)
    def calculate(self):
        s=self.e._solver;d=s.mjw_data;m=s.mjw_model
        xipos=wp.to_torch(d.xipos)
        for i,(b,body) in enumerate(zip(self.ids,self.body)):
            self.points[i].copy_(xipos[:,b])
            mjw.jac(m,d,self.jac,None,self.points_wp[i],body)
            self.jacs[:,i*2:i*2+2].copy_(wp.to_torch(self.jac)[:,:2])
        for j in range(10):
            wp.to_torch(self.y).copy_(self.jacs[:,j]);mjw.solve_m(m,d,self.x,self.y)
            self.inverses[:,:,j].copy_(wp.to_torch(self.x))
        return self.jacs,self.inverses
    def basis(self):
        if self.graph is None:
            stream=torch.cuda.Stream()
            stream.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(stream),wp.ScopedStream(wp.stream_from_torch(stream)):
                for _ in range(3):self.calculate()
            torch.cuda.current_stream().wait_stream(stream)
            self.graph=torch.cuda.CUDAGraph()
            warp_stream=wp.stream_from_torch(stream)
            with wp.ScopedStream(warp_stream):
                with torch.cuda.graph(self.graph,stream=stream):
                    with wp.ScopedCapture(stream=warp_stream,external=True):
                        self.calculate()
        self.graph.replay()
        return self.jacs,self.inverses
    def apply(self,rows,desired):
        e=self.e;s=e._solver;d=s.mjw_data;state=e._sim_state.raw_state
        e._sim_state.pre_step_update();s._update_mjc_data(d,e._sim_model,state)
        mjw.kinematics(s.mjw_model,d);mjw.com_pos(s.mjw_model,d);mjw.crb(s.mjw_model,d);mjw.factor_m(s.mjw_model,d)
        jac,inv=self.basis();j=jac[rows];a=inv[rows]
        mobility=j@a;wanted=desired.flatten(1)
        impulses=torch.linalg.solve(mobility,wanted[:,:,None]);delta=(a@impulses).squeeze(-1)
        measured=(j@delta[:,:,None]).squeeze(-1);error=(measured-wanted).abs().amax(-1)
        if not torch.isfinite(delta).all() or float(error.max())>.002:raise RuntimeError('Articulated kick solve failed')
        wp.to_torch(d.qvel)[rows]+=delta
        s._update_newton_state(e._sim_model,state,d,state);e._sim_state.post_step_update();e.refresh_body_velocities()
        return error

def reference_basis(k,prepare=True):
    s=k.e._solver;d=s.mjw_data;m=s.mjw_model
    if prepare:
        mjw.kinematics(m,d);mjw.com_pos(m,d);mjw.crb(m,d);mjw.factor_m(m,d)
    xipos=wp.to_torch(d.xipos);mat=[]
    for b,body in zip(k.ids,k.body):
        point=wp.from_torch(xipos[:,b].contiguous(),dtype=wp.vec3)
        mjw.jac(m,d,k.jac,None,point,body);mat.append(wp.to_torch(k.jac)[:,:2].clone())
    jac=torch.cat(mat,1);inverse=[]
    for j in range(10):
        wp.to_torch(k.y).copy_(jac[:,j]);mjw.solve_m(m,d,k.x,k.y);inverse.append(wp.to_torch(k.x).clone())
    return jac,torch.stack(inverse,-1)

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6820)
    cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    e=PerturbedOmniEnv(cfg,ec,2048,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
    run=ROOT/'runs'/sys.argv[1];b=json.loads((run/'backup_status.json').read_text());restore(a,run/Path(b['key']).name)
    a._init_train();a.set_mode(AgentMode.TRAIN);a._curr_obs,a._curr_info=a._reset_envs()
    s=e._engine._solver;m=s.mj_model
    report=dict(checkpoint=b,model={k:getattr(m,k).tolist() if hasattr(getattr(m,k),'tolist') else getattr(m,k) for k in ['ngeom','nv','njnt','npair','nexclude','geom_type','geom_bodyid','geom_contype','geom_conaffinity','geom_condim','jnt_limited','dof_frictionloss']},warp_model={k:getattr(s.mjw_model,k).numpy().tolist() if isinstance(getattr(s.mjw_model,k),wp.array) else str(getattr(s.mjw_model,k)) for k in ['geom_pair'] if hasattr(s.mjw_model,k)})
    (OUT/'model-capacity.json').write_text(json.dumps(report,indent=2))
    k=ArticulatedKicks(e._engine);g=GraphKicks(e._engine)
    checks=[]
    for i in range(8):
        if i:a._curr_obs,a._curr_info=a._reset_envs()
        e._engine._sim_state.pre_step_update();s._update_mjc_data(s.mjw_data,e._engine._sim_model,e._engine._sim_state.raw_state)
        j,inv=reference_basis(k);j2,inv2=reference_basis(k,False);gj,gi=g.basis();torch.cuda.synchronize()
        checks.append(dict(jac_max=float((j-gj).abs().max()),inverse_max=float((inv-gi).abs().max()),reference_jac_variation=float((j-j2).abs().max()),reference_inverse_variation=float((inv-inv2).abs().max())))
        (OUT/'kick-graph-checks.json').write_text(json.dumps(checks,indent=2))
        # Parallel atomic reductions already vary between unmodified calls.
        # Record that floor and accept only FP32-scale differences here.
        torch.testing.assert_close(gj,j,atol=2e-6,rtol=2e-6)
        torch.testing.assert_close(gi,inv,atol=2e-5,rtol=2e-5)
        wanted=torch.randn((len(j),10,1),device=j.device)
        delta=(inv@torch.linalg.solve(j@inv,wanted)).squeeze(-1)
        candidate=(gi@torch.linalg.solve(gj@gi,wanted)).squeeze(-1)
        physical=(j@(candidate-delta)[:,:,None]).abs().amax()
        checks[-1]['resulting_body_velocity_difference']=float(physical)
        assert float(physical)<2e-4
    report['basis_checks']=checks
    timings=[]
    for mode in [False,True,True,False]:
        torch.cuda.synchronize();start=time.perf_counter()
        for _ in range(20):g.basis() if mode else reference_basis(k,False)
        torch.cuda.synchronize();timings.append(dict(graph=mode,seconds=(time.perf_counter()-start)/20))
    report['basis_times']=timings
    (OUT/'kick-graph-basis.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(checks=checks,timings=timings)),flush=True)
    final=next(v for v in e.__dict__.values() if isinstance(v,final_locomotion.FinalLocomotion))
    updates=[]
    for mode in [False,True,True,False]:
        final.kicker=g if mode else k
        for _ in range(2):
            torch.cuda.synchronize();start=time.perf_counter();a._train_iter();torch.cuda.synchronize()
            updates.append(dict(graph=mode,seconds=time.perf_counter()-start));print(json.dumps(updates[-1]),flush=True)
    report['update_times']=updates
    (OUT/'kick-graph-complete.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':
    try:main()
    except Exception:(OUT/'kick-graph-failure.txt').write_text(traceback.format_exc());raise
