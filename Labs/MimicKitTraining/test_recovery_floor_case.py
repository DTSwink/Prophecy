"""Same saved policy and authored starts, floor guard off/on; no learning."""
import os,sys,json,time,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
os.environ['PYGLET_HEADLESS']='true'
import numpy as np,torch,warp as wp,yaml
from scipy.spatial.transform import Rotation
from recovery_omni import RecoveryOmniEnv
from omni_policy import OmniPPOAgent,circular_phase
from learning.base_agent import AgentMode
from util import mp_util
from resume import restore

def bottoms(env,geometry):
    ids=env._recovery_ids
    p=env._engine.get_body_pos(env._get_char_id())[ids].cpu().numpy()
    q=env._engine.get_body_rot(env._get_char_id())[ids].cpu().numpy()
    low=[]
    for shape in geometry['shapes']:
        b=geometry['names'].index(shape['bone']);rot=Rotation.from_quat(q[:,b]);centre=p[:,b]+rot.apply(shape['position'])
        axes=np.array(shape['axes'])
        if shape['kind']=='capsule':extent=shape['radius']+.5*shape['length']*abs(rot.apply(axes[2])[:,2])
        elif shape['kind']=='sphere':extent=shape['radius']
        else:extent=sum(abs(rot.apply(axis)[:,2])*v*.5 for axis,v in zip(axes,shape['dimensions']))
        low.append(centre[:,2]-extent)
    return np.array(low).T

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default='matched-policy');parser.add_argument('--parallel',action='store_true');parser.add_argument('--accelerated',action='store_true');args=parser.parse_args();tag=args.tag
    if args.accelerated:
        import importlib.util
        sys.path.insert(0,str(ROOT/'Labs/MimicKitTransfer'))
        from make_register_contact_candidate import generate
        spec=importlib.util.spec_from_file_location('block_contact_gpu',generate(accelerated=True))
        candidate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=candidate;spec.loader.exec_module(candidate)
    if args.parallel:
        sys.path.insert(0,str(ROOT/'Labs/MimicKitTransfer'))
        from floor_projection_guard import FloorProjectionGuard
        from floor_projection_parallel import apply_parallel
        FloorProjectionGuard.apply=apply_parallel
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6793)
    os.chdir(ROOT/'Saved/MimicKit/vendor/MimicKit')
    out=ROOT/'Saved/MimicKitEquipment';folder=out/'recovery-preflight';geometry=json.loads((out/'geometry.json').read_text())
    reports=[];arrays={}
    for enabled in (False,True):
        torch.manual_seed(173)
        cfg,ec,ac=[yaml.safe_load((folder/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
        cfg['idle_row_fraction']=.8;ec['transfer_floor_aware_projection']=enabled
        env=RecoveryOmniEnv(cfg,ec,32,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
        restore(agent,out/'floor-recovery-study-checkpoint.zip');agent.eval();agent.set_mode(AgentMode.TEST)
        # This probe overrides private reset times after normal sampling.
        # Evaluate those explicit times, rather than the normal sampled-frame cache.
        env._cache_recovery_spawns=False
        original=env._reset_ref_motion
        def reset(ids):
            original(ids);rows=ids[env._recovery_rows[ids]]
            clips=torch.tensor([1,1,0,1],device=env._device);times=torch.tensor([16/30,20/30,17/30,27/30],device=env._device)
            env._recovery_motion[rows]=clips[rows%4];env._recovery_start[rows]=times[rows%4]
            phase=circular_phase(env._recovery_start[rows]/env._recovery_lib.get_motion_length(env._recovery_motion[rows]))
            env._feedback_phase[rows]=phase;env._pending_phase[rows]=phase
            env._replace_recovery_reference();env._ref_dof_pos[rows]=env._recovery_lib.joint_rot_to_dof(env._ref_joint_rot[rows])
        env._reset_ref_motion=reset
        obs,info=env.reset();heights=[bottoms(env,geometry)];first=np.full(len(env._recovery_ids),-1)
        start=time.perf_counter()
        for tick in range(1,31):
            with torch.no_grad():action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
            heights.append(bottoms(env,geometry));end=done[env._recovery_ids].cpu().numpy()!=0
            first[(first<0)&end]=tick
            assert torch.isfinite(obs).all()
        elapsed=time.perf_counter()-start;env._engine.validate_transfer_solver()
        h=np.array(heights);arrays['guard_'+str(enabled)]=h;cases=[]
        worlds=env._recovery_ids.cpu().numpy();motion=env._recovery_motion[env._recovery_ids].cpu().tolist()
        for i,w in enumerate(worlds):
            last=int(first[i]) if first[i]>=0 else 30
            cases.append(dict(world=int(w),case=int(w%4),drawn=bool(env._equipment[env._motion_ids[w]]),motion=motion[i],
                first_done_tick=last,start_depth_cm=float(max(0,-h[0,i].min())*100),
                peak_depth_cm=float(max(0,-h[:last+1,i].min())*100),first_three_ticks_depth_cm=float(max(0,-h[:4,i].min())*100)))
        reports.append(dict(enabled=enabled,seconds=elapsed,cases=cases));print(json.dumps(reports[-1]),flush=True)
        del agent,env
    (out/'floor-recovery'/(tag+'.json')).write_text(json.dumps(reports,indent=2))
    np.savez_compressed(out/'floor-recovery'/(tag+'-heights.npz'),**arrays)
if __name__=='__main__':main()
