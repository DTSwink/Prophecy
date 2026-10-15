"""Reapply the captured action prefix to a common physical state, with telemetry."""
import argparse,json
import numpy as np
import torch
import warp as wp
import mujoco
from recovery_env import RecoveryEnv,OUT


def main():
    p=argparse.ArgumentParser();p.add_argument('--kp',type=float,default=1);p.add_argument('--kd',type=float,default=1)
    p.add_argument('--integrator',default='euler');p.add_argument('--label',default='failure-replay')
    p.add_argument('--source',default='runs/diagnose_05/failure-prefix.npz')
    p.add_argument('--native-motors',action='store_true')
    p.add_argument('--relative-targets',action='store_true')
    p.add_argument('--contacts',type=int,default=256);p.add_argument('--constraints',type=int,default=768)
    p.add_argument('--ccd-iterations',type=int,default=50);p.add_argument('--no-gyroscopic-forces',action='store_true')
    p.add_argument('--subdivide',type=int,default=1);args=p.parse_args()
    if args.native_motors and (args.kp!=1 or args.kd!=1):
        raise ValueError('Native gain changes require rebuilding the actuator model, not changing only the callback gains')
    torch.set_num_threads(1);wp.init()
    source=np.load(OUT/args.source)
    env=RecoveryEnv(16,auto_reset=False,integrator='euler' if args.integrator=='rk4' else args.integrator,
        native_motors=args.native_motors,relative_targets=args.relative_targets,
        contact_capacity=args.contacts,constraint_capacity=args.constraints,ccd_iterations=args.ccd_iterations,gyroscopic_forces=not args.no_gyroscopic_forces)
    if args.integrator=='rk4':
        # Warp supports RK4; the pinned mjlab convenience configuration exposes
        # only Euler/implicitfast. This is a diagnostic, not a training default.
        env.sim.wp_model.opt.integrator=mujoco.mjtIntegrator.mjINT_RK4.value
        env.sim.create_graph()
    env.sim.wp_model.opt.timestep.fill_(1/(240*args.subdivide))
    gains=env.controller.gains.numpy();gains[:,0]*=args.kp;gains[:,1]*=args.kd
    wp.copy(env.controller.gains,wp.array(gains,dtype=wp.vec3,device='cuda'))
    env.qpos.copy_(torch.tensor(source['qpos'][0],device='cuda')[None,:]);env.qvel.copy_(torch.tensor(source['qvel'][0],device='cuda')[None,:])
    rows=[]
    steps=480*args.subdivide
    for step in range(steps):
        if step//(8*args.subdivide)<len(source['actions']):
            env.controller.actions.copy_(torch.tensor(source['actions'][step//(8*args.subdivide)],device='cuda')[None,:].clamp(-env.controller.action_bound,env.controller.action_bound))
        wp.capture_launch(env.sim.step_graph)
        q=env.qpos.cpu().numpy();v=env.qvel.cpu().numpy()
        rows.append({'step':step,'maxv':float(np.nanmax(abs(v))),'maxpos':float(np.nanmax(abs(q[:,:3]))),
                     'rows':int(env.sim.wp_data.nefc.numpy().max()),'finite':bool(np.isfinite(q).all() and np.isfinite(v).all())})
        if not rows[-1]['finite'] or rows[-1]['maxv']>1000:break
    result={'kp':args.kp,'kd':args.kd,'integrator':args.integrator,'complete':len(rows)==steps,'rows':rows,
            'source':args.source,'physics_hz':240*args.subdivide,'contact_capacity':args.contacts,'constraint_capacity':args.constraints,
            'capacity_peaks':env.controller.capacity_max.numpy().tolist(),
            'ccd_iterations':args.ccd_iterations,'gyroscopic_forces':not args.no_gyroscopic_forces,
            'controller':env.controller.contract,'rig_sha256':env.metadata['rig_sha256'],
            'passed':len(rows)==steps and max(r['maxv'] for r in rows)<500 and not env.capacity_overflow.item()}
    (OUT/(args.label+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({**{k:v for k,v in result.items() if k!='rows'},'last':rows[-1],'peakv':max(r['maxv'] for r in rows)},indent=2))


if __name__=='__main__':main()
