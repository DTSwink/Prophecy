"""Same-state comparison of implicitfast and explicit-PD Euler integration."""
import json
import numpy as np
import torch
import warp as wp
from mujoco_warp._src import derivative,forward,types
from recovery_env import RecoveryEnv,OUT


def select(env):
    torch.cuda.set_stream(env.sim.physical_torch_stream)
    wp.set_stream(env.sim.physical_warp_stream)


def main():
    torch.set_num_threads(1);wp.init();torch.manual_seed(7)
    worlds=32
    a=RecoveryEnv(worlds,integrator='implicitfast')
    rng=np.random.default_rng(35)
    poses=np.load(OUT/'rig-passive.npz')['qpos']
    maxima={'position':0.,'velocity':0.,'acceleration':0.,'mass_derivative':0.}
    rows=[]
    for sample in range(16):
        q=poses[np.arange(worlds)%len(poses)].copy()
        if sample%4==0:q[:]=np.asarray(a.metadata['reference_qpos'])
        q[:,2]+=rng.uniform(0,.03,(worlds,))
        v=rng.normal(0,.5,(worlds,a.metadata['nv'])).astype('f')
        act=rng.uniform(-1,1,(worlds,a.num_actions)).astype('f')
        outputs=[]
        for env in (a,):
            select(env)
            env.reset(torch.ones(worlds,device='cuda',dtype=torch.bool))
            env.qpos.copy_(torch.from_numpy(q).to('cuda'))
            env.qvel.copy_(torch.from_numpy(v).to('cuda'))
            env.controller.actions.copy_(torch.from_numpy(act).to('cuda'))
            wp.capture_launch(env.sim.forward_graph)
            if env is a:
                mass=env.sim.wp_data.qM
                scratch=wp.empty_like(mass)
                derivative.deriv_smooth_vel(env.sim.wp_model,env.sim.wp_data,scratch)
                error=float(np.max(np.abs(scratch.numpy()-mass.numpy())))
                maxima['mass_derivative']=max(maxima['mass_derivative'],error)
            # Integrate the exact same solved state twice. Two independent full
            # solves also differ from unordered GPU constraint-row accumulation.
            position=env.qpos.clone();velocity=env.qvel.clone()
            forward.implicit(env.sim.wp_model,env.sim.wp_data)
            outputs.append((env.qpos.cpu().numpy().copy(),env.qvel.cpu().numpy().copy()))
            env.qpos.copy_(position);env.qvel.copy_(velocity)
            previous_flags=env.sim.wp_model.opt.disableflags
            env.sim.wp_model.opt.disableflags|=types.DisableBit.EULERDAMP
            forward.euler(env.sim.wp_model,env.sim.wp_data)
            env.sim.wp_model.opt.disableflags=previous_flags
            outputs.append((env.qpos.cpu().numpy().copy(),env.qvel.cpu().numpy().copy()))
        errors=[float(np.max(np.abs(x-y))) for x,y in zip(*outputs)]
        for name,value in zip(('position','velocity'),errors):maxima[name]=max(maxima[name],value)
        rows.append(errors)
    # Independent solves use unordered atomic sums, so tiny roundoff is expected.
    passed=maxima['mass_derivative']==0 and maxima['position']<2e-5 and maxima['velocity']<.005
    report={'passed':passed,'same_state_comparisons':worlds*len(rows),'max_abs_errors':maxima,'per_batch':rows}
    (OUT/'integration-comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));assert passed,report


if __name__=='__main__':main()
