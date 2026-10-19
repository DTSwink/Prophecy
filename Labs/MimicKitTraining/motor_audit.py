"""Isolated animation-following motor audit. Never launches or changes training.

Uses a hash-checked copy of the stopped run's source and motion package. The
controller supplies velocity commands at 30 Hz; the deployed 240 Hz physics,
floating root, contacts, inertia, limits and motor law remain active.
"""
import os,sys,json,time,hashlib,zipfile,argparse,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitMotorAudit'
SOURCE=OUT/'source'
EXPECTED_SOURCE='ce212b22640f5caa7456279e6239657f61f2a522e5a68497019f716cfe454640'
os.environ.setdefault('PYGLET_HEADLESS','true')
os.environ.setdefault('OMP_NUM_THREADS','1')


def prepare():
    archive=OUT/'source.zip'
    if not archive.exists():archive=ROOT/'Saved/MimicKitEquipment/source.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==EXPECTED_SOURCE
    SOURCE.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            target=(SOURCE/name).resolve()
            assert target.is_relative_to(SOURCE.resolve())
            if name.endswith('/'):continue
            data=z.read(name)
            if target.exists():assert target.read_bytes()==data,('Audit source modified',name)
            else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if archive.parent==OUT:
        # After production resumes, retain this audit's original external data.
        assert (SOURCE/'prepared/env_config.yaml').exists() and (SOURCE/'motions').is_dir()
        return
    for directory in ['motions','prepared']:
        origin=ROOT/'Saved/MimicKitEquipment/package'/directory
        for src in origin.rglob('*'):
            if src.is_file():
                dest=SOURCE/directory/src.relative_to(origin);dest.parent.mkdir(parents=True,exist_ok=True)
                if not dest.exists():shutil.copy2(src,dest)
                else:assert dest.read_bytes()==src.read_bytes(),src


prepare()
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(SOURCE/'pipeline'),str(SOURCE/'MimicKit/mimickit')]
import numpy as np,torch,warp as wp,yaml
from omni_walk import OmniWalkEnv
from uefn_engine import build_uefn_engine
from anim.kin_char_model import JointType
from util import torch_util as q,mp_util
from envs.base_env import EnvMode


@wp.kernel(enable_backward=False)
def tally(torque:wp.array2d(dtype=float),qvel:wp.array2d(dtype=float),dofs:wp.array(dtype=int),
          caps:wp.array(dtype=float),active:wp.array(dtype=int),peak:wp.array2d(dtype=float),
          capped:wp.array2d(dtype=int),speed:wp.array2d(dtype=float),count:wp.array2d(dtype=int)):
    w,j=wp.tid()
    if active[w]!=0:
        value=wp.abs(torque[w,j])
        peak[w,j]=wp.max(peak[w,j],value)
        speed[w,j]=wp.max(speed[w,j],wp.abs(qvel[w,dofs[j]]))
        capped[w,j]+=int(value>=.99*caps[j])
        count[w,j]+=1


class AuditEnv(OmniWalkEnv):
    def _build_engine(self,config,*args,**kwargs):
        # Install instrumentation before graph construction via an isolated class.
        folder=Path(config['uefn_asset_directory']).parent/'MimicKitTransfer'
        sys.path.insert(0,str(folder))
        from contact_engine import ContactTransferEngine
        class Instrumented(ContactTransferEngine):
            def _build_solver(engine):
                super(Instrumented,engine)._build_solver()
                motor=engine._uefn_motors;s=engine._solver
                # Explicit diagnostic variables only; default equals deployed values.
                motor.gains.assign(motor.gains.numpy()*ARGS.motor_gain_scale)
                motor.upper.assign(motor.upper.numpy()*ARGS.torque_scale)
                motor.lower.assign(-motor.upper.numpy())
                n=engine.get_num_envs();k=len(motor.ids)
                engine.audit_active=wp.ones(n,dtype=int,device=engine._device)
                engine.audit_peak=wp.zeros((n,k),device=engine._device)
                engine.audit_capped=wp.zeros((n,k),dtype=int,device=engine._device)
                engine.audit_speed=wp.zeros((n,k),device=engine._device)
                engine.audit_count=wp.zeros((n,k),dtype=int,device=engine._device)
                old=s._mujoco_warp_step
                def step():
                    old()
                    wp.launch(tally,dim=(n,k),inputs=[motor.torque,s.mjw_data.qvel,motor.dofs,motor.upper,
                        engine.audit_active,engine.audit_peak,engine.audit_capped,engine.audit_speed,engine.audit_count],device=engine._device)
                s._mujoco_warp_step=step
        return Instrumented(config,*args,**kwargs)

    def _reset_ref_motion(self,ids):
        # Exact reference pose AND velocity, at an explicitly enumerated phase.
        if not hasattr(self,'audit_ids'):return super()._reset_ref_motion(ids)
        motions=self.audit_ids[ids];times=self.audit_times[ids]
        self._motion_ids[ids]=motions;self._motion_time_offsets[ids]=times
        values=self._motion_lib.calc_motion_frame(motions,times)
        for dest,value in zip((self._ref_root_pos,self._ref_root_rot,self._ref_root_vel,self._ref_root_ang_vel,self._ref_joint_rot,self._ref_dof_vel),values):dest[ids]=value
        pos,rot=self._kin_char_model.forward_kinematics(self._ref_root_pos,self._ref_root_rot,self._ref_joint_rot)
        self._ref_body_pos.copy_(pos);self._ref_body_rot.copy_(rot)
        self._ref_dof_pos[ids]=self._motion_lib.joint_rot_to_dof(values[4])


def main():
    global ARGS
    p=argparse.ArgumentParser();p.add_argument('--name',required=True)
    p.add_argument('--device',default='cuda:0');p.add_argument('--phases',type=int,default=4)
    p.add_argument('--clips',nargs='*');p.add_argument('--seconds',type=float,default=6)
    p.add_argument('--pose-gain',type=float,default=15)
    p.add_argument('--command-limit',choices=['stock','reference'],default='reference')
    p.add_argument('--motor-gain-scale',type=float,default=1)
    p.add_argument('--torque-scale',type=float,default=1)
    p.add_argument('--inverse-screen',action='store_true')
    p.add_argument('--controller',choices=['joint','dynamics','policy'],default='joint')
    p.add_argument('--search',action='store_true')
    p.add_argument('--search-seed')
    p.add_argument('--search-windowed',action='store_true')
    ARGS=p.parse_args();a=ARGS
    result=OUT/(a.name+'.json');assert not result.exists(),result
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(137);np.random.seed(137)
    wp.init();wp.set_device(a.device);mp_util.init(0,1,a.device,6736)
    os.chdir(SOURCE/'MimicKit')
    checkpoint=ROOT/'Saved/MimicKitEquipment/latest-stopped.zip'
    with zipfile.ZipFile(checkpoint) as z:
        cfg={n:yaml.safe_load(z.read(n+'_config.yaml').decode().replace('/workspace/mimickit_trial',SOURCE.as_posix())) for n in ['env','engine']}
    # No adaptation, optimization, resets-on-failure or learned actor in this test.
    cfg['env'].pop('adaptive_motion_rows',None);cfg['env']['episode_length']=a.seconds
    motions=yaml.safe_load(Path(cfg['env']['motion_file']).read_text().replace('/workspace/mimickit_trial',SOURCE.as_posix()))
    local=OUT/'motions.yaml';local.write_text(yaml.safe_dump(motions));cfg['env']['motion_file']=str(local)
    manifest=json.loads(Path(cfg['env']['omni_manifest']).read_text())
    active_names=[Path(r['file']).stem for r in motions['motions']]
    selected=[i for i,n in enumerate(active_names) if not a.clips or n in a.clips]
    assert selected
    ids=np.repeat(selected,a.phases);phases=np.tile(np.arange(a.phases)/a.phases,len(selected));worlds=len(ids)
    if a.search:
        assert len(selected)==1 and a.controller=='policy'
        phases[:]=0.
    assert worlds>=2
    begun=time.perf_counter();env=AuditEnv(cfg['env'],cfg['engine'],worlds,a.device,False)
    e=env._engine;model=env._kin_char_model;lib=env._motion_lib;char=env._get_char_id()
    env.audit_ids=torch.tensor(ids,device=a.device);env.audit_times=torch.tensor(phases,device=a.device,dtype=torch.float32)*lib.get_motion_lengths()[env.audit_ids]
    motor=e._uefn_motors
    if a.inverse_screen:
        from motor_dynamics_audit import screen
        screen(env,selected,active_names,result,a)
        return
    bounds=lib._frame_dof_vel.abs().amax(0)+torch.tensor(motor.upper.numpy()/motor.gains.numpy(),device=a.device)
    if a.command_limit=='stock':bounds.fill_(2*np.pi)
    env._action_bound_high=bounds;env._action_bound_low=-bounds
    mapping=torch.zeros((34,(model.get_num_joints()-1)*3),device=a.device)
    names=[]
    for j in range(1,model.get_num_joints()):
        joint=model.get_joint(j);start=joint.dof_idx
        if joint.joint_type==JointType.SPHERICAL:
            mapping[start:start+3,(j-1)*3:j*3]=torch.eye(3,device=a.device);names.extend([model.get_body_name(j)+':'+str(i) for i in range(3)])
        elif joint.joint_type==JointType.HINGE:
            mapping[start,(j-1)*3:j*3]=joint.axis;names.append(model.get_body_name(j))
    env.set_mode(EnvMode.TEST);obs,_=env.reset()
    controller=None
    agent=None
    if a.controller=='policy':
        from omni_policy import OmniPPOAgent
        from learning.base_agent import AgentMode
        with zipfile.ZipFile(checkpoint) as z:
            agent_cfg=yaml.safe_load(z.read('agent_config.yaml'))
            model_path=OUT/'control-policy.pt'
            model_path.write_bytes(z.read('model.pt'))
        agent=OmniPPOAgent(agent_cfg,env,a.device);agent.load(str(model_path));agent.eval();agent.set_mode(AgentMode.TEST)
        model_path.unlink() # The verified checkpoint ZIP remains the only copy.
    if a.search:
        from motor_search import search
        search(env,agent,result,a,active_names[selected[0]])
        return
    if a.controller=='dynamics':
        from motor_dynamics_audit import WholeBodyController
        controller=WholeBodyController(env)
    for name in ['audit_peak','audit_capped','audit_speed','audit_count']:getattr(e,name).zero_()
    active=wp.to_torch(e.audit_active);active.fill_(1)
    duration=torch.full((worlds,),a.seconds,device=a.device);why=torch.zeros(worlds,device=a.device,dtype=torch.long)
    first_solver_error=torch.full((worlds,),-1,device=a.device,dtype=torch.long)
    solver_error_while_active=torch.zeros(worlds,device=a.device,dtype=torch.bool)
    worst=torch.zeros(worlds,device=a.device);clip_count=torch.zeros((worlds,34),device=a.device);max_cmd=torch.zeros_like(clip_count)
    traces=[];commands=[];targets=[]
    trace_ids=torch.arange(min(worlds,8),device=a.device)
    for tick in range(round(a.seconds*30)):
        ids_t=env._motion_ids;times=env._get_motion_times()
        _,_,_,_,target,_=lib.calc_motion_frame(ids_t,times)
        _,_,_,_,future,_=lib.calc_motion_frame(ids_t,times+1/30)
        feedforward=model.compute_dof_vel(target,future,torch.full((worlds,1),1/30,device=a.device))
        actual=model.dof_to_rot(e.get_dof_pos(char))
        delta=q.quat_to_exp_map(q.quat_mul(q.quat_conjugate(actual),target))
        error=delta.reshape(worlds,-1)@mapping.T
        cmd=feedforward+a.pose_gain*error
        if controller is not None:cmd=controller.command(active,tick)
        if agent is not None:
            with torch.no_grad():cmd,_=agent._decide_action(obs,{})
        clip_count+=(cmd.abs()>bounds)*active[:,None];max_cmd=torch.maximum(max_cmd,cmd.abs()*active[:,None])
        obs,_,done,_=env.step(cmd)
        error_flags=wp.to_torch(e.transfer_contact.error)
        new_error=(error_flags!=0)&(first_solver_error<0)
        first_solver_error[new_error]=tick+1
        numerical_failure=(error_flags!=0)&(active!=0)
        solver_error_while_active|=numerical_failure
        distances=env.target_distances_sq.sqrt().amax(-1)
        worst=torch.maximum(worst,distances*active)
        failed=((done==1)|numerical_failure)&(active!=0)
        duration[failed]=(tick+1)/30;why[failed]=1;active[failed]=0
        why[numerical_failure]=2
        if not torch.isfinite(e.get_body_pos(char)).all():raise RuntimeError('Nonfinite isolated audit state')
        if tick%30==0:print('TICK',tick,'active',int(active.sum()),flush=True)
        traces.append(torch.cat([e.get_body_pos(char)[trace_ids],e.get_body_rot(char)[trace_ids]],-1).cpu().numpy())
        targets.append(torch.cat([env.reward_target_pos[trace_ids],env.reward_target_rot[trace_ids]],-1).cpu().numpy())
        commands.append(cmd[trace_ids].cpu().numpy())
    try:warning=e.validate_transfer_solver()
    except FloatingPointError as error:
        # Other worlds continue after a row's first failed episode. Solver
        # errors in that already-excluded tail do not invalidate surviving rows.
        warning=dict(message=str(error),first_error_tick=first_solver_error.tolist(),
            error_during_measured_episode=solver_error_while_active.tolist())
    peak=e.audit_peak.numpy();sat=e.audit_capped.numpy()/np.maximum(e.audit_count.numpy(),1)
    rows=[]
    for i,mid in enumerate(ids):
        rows.append(dict(motion=active_names[mid],phase=float(phases[i]),seconds=float(duration[i]),passed=not bool(why[i]),
            failure_reason=int(why[i]),first_solver_error_tick=int(first_solver_error[i]),solver_error_during_episode=bool(solver_error_while_active[i]),
            max_target_distance_m=float(worst[i]),torque_peak=peak[i].tolist(),torque_cap_fraction=sat[i].tolist(),
            command_peak=max_cmd[i].tolist(),command_clipped_ticks=clip_count[i].tolist(),angular_speed_peak=e.audit_speed.numpy()[i].tolist()))
    report=dict(settings=vars(a),worlds=worlds,passed=sum(r['passed'] for r in rows),rows=rows,motor_names=names,
        gains=motor.gains.numpy().tolist(),torque_caps=motor.upper.numpy().tolist(),command_bounds=bounds.tolist(),
        elapsed_seconds=time.perf_counter()-begun,source_sha256=EXPECTED_SOURCE,checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        warnings=warning,controller=a.controller+'; no root actuation or virtual supports',
        limitations='A failed tracking controller does not prove torque insufficiency. Recorded maxima exclude post-failure motion. No optimization, no production changes.')
    result.write_text(json.dumps(report,indent=2));np.savez_compressed(OUT/(a.name+'_traces.npz'),pose=traces,target=targets,commands=commands,worlds=trace_ids.cpu().numpy())
    print('RESULT',json.dumps({k:report[k] for k in ['worlds','passed','elapsed_seconds']}),flush=True)


if __name__=='__main__':main()
