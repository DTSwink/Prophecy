"""Local-only controlled contact/limit projection trace; no PPO or cloud changes."""
import json
import sys
from pathlib import Path
import preflight as setup
import numpy as np
import torch, yaml, warp as wp, mujoco


def main():
    setup.os.chdir(setup.PACKAGE/'MimicKit')
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    wp.init();wp.set_device('cuda:0');setup.mp_util.init(0,1,'cuda:0',6744)
    cfg,ec=[yaml.safe_load((setup.OUT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine')]
    cfg['rand_reset']=False
    env=setup.CrawlEnv(cfg,ec,2,'cuda:0',False)
    idle=int(torch.nonzero(env._gaits==-1)[0]);env._fixed_motion_ids.fill_(idle)
    engine=env._engine;engine._graph=None
    solver=engine._solver;m=solver.mj_model;d=solver.mjw_data
    cpu=mujoco.MjData(m)
    hands=[i for i in range(m.ngeom) if 'hand_' in m.geom(i).name]
    assert len(hands)==2
    def bottoms():
        cpu.qpos[:]=d.qpos.numpy()[0];mujoco.mj_kinematics(m,cpu)
        return [float(cpu.geom_xpos[g,2]-np.abs(cpu.geom_xmat[g].reshape(3,3)[2])@m.geom_size[g]) for g in hands]
    original=engine.transfer_projection.apply;reports=[]
    ground=None
    if '--ground' in sys.argv:
        from ground_position import GroundPosition
        ground=GroundPosition(m,solver.mjw_model,d,'cuda:0')
    for projection in ((True,) if ground else (True,False)):
        trace=[]
        def measured(inverse,**kwargs):
            before=bottoms()
            if projection:original(inverse,**kwargs)
            if ground:
                velocity=d.qvel.numpy().copy()
                ground.apply(inverse)
                np.testing.assert_array_equal(d.qvel.numpy(),velocity)
            after=bottoms()
            trace.append(dict(before=before,after=after))
        engine.transfer_projection.apply=measured
        env.reset();frames=[]
        # mjw_data.qpos syncs on the next engine step; it is stale just after
        # env.reset. Do not present that stale buffer as the starting pose.
        initial='reference reset; measured CPU qpos becomes current on first substep'
        for tick in range(60):
            env.step(torch.zeros((2,34),device='cuda:0'))
            frames.append(bottoms())
        p=engine.transfer_contact.p
        reports.append(dict(angular_position_projection=projection,ground_position_recovery=bool(ground),initial=initial,
            ticks=frames,substeps=trace,solver_errors=engine.transfer_contact.error.numpy().tolist(),
            contact_count=p.ncontact.numpy().tolist()))
        print(json.dumps(dict(projection=projection,initial=initial,minimum=np.min(frames,axis=0).tolist(),
            maximum_single_projection_drop=np.max(np.array([x['before'] for x in trace])-np.array([x['after'] for x in trace]),axis=0).tolist())),flush=True)
    output=setup.OUT/'hand-penetration';output.mkdir(exist_ok=True)
    name='ground-prototype.json' if ground else 'projection-ablation.json'
    if '--output-name' in sys.argv:
        name=sys.argv[sys.argv.index('--output-name')+1]
        assert Path(name).name==name
    (output/name).write_text(json.dumps(reports,indent=2))


if __name__=='__main__':main()
