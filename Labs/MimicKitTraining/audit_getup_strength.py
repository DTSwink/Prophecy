"""Isolated CPU native-MuJoCo strength audit; never edits the live trainer."""
import os,sys,json,zipfile,io,time,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment/upperbody-audit'
SOURCE=OUT/'source'
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit')]
os.environ['PYGLET_HEADLESS']='true';os.environ['OMP_NUM_THREADS']='1'
import numpy as np,torch,warp as wp,newton,mujoco,yaml
from scipy.spatial.transform import Rotation as R
from types import SimpleNamespace
from engines.newton_engine import NewtonEngine
from native_uefn_engine import configure_native_model
from torque_envelope import apply_torque_envelope
from recovery_omni import RecoveryOmniEnv
import omni_walk
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from envs.base_env import EnvMode
from util import mp_util


class CpuEngine(NewtonEngine):
    def __init__(self,config,*args,**kwargs):
        self.cfg=config;super().__init__(config,*args,**kwargs)
    def _build_solver(self):
        apply_torque_envelope(self._sim_model,self.cfg['uefn_motor_torque_caps_nm'])
        self._sim_model.joint_armature.zero_()
        self._solver=newton.solvers.SolverMuJoCo(self._sim_model,use_mujoco_cpu=True,
            solver='newton',njmax=450,nconmax=150,impratio=10,iterations=100,ls_iterations=50)
        s=self._solver;m=s.mj_model
        meta=json.loads((Path(self.cfg['uefn_asset_directory'])/'limits.json').read_text())
        refs,_=configure_native_model(m,meta)
        self.balls=[(int(m.jnt_qposadr[j]),R.from_quat(refs[j])) for j in range(m.njnt) if m.jnt_type[j]==1]
        self.motors=np.flatnonzero(m.actuator_biasprm[:,2]!=0)
        gains=-m.actuator_biasprm[self.motors,2]
        caps=np.array([m.actuator_forcerange[a,1] if m.actuator_forcelimited[a] else m.jnt_actfrcrange[m.actuator_trnid[a,0],1] for a in self.motors])
        self._uefn_motors=SimpleNamespace(gains=wp.array(gains.astype(np.float32),device='cpu'),upper=wp.array(caps.astype(np.float32),device='cpu'))
        bodies=[j['body'] for j in meta['joints']]
        self.names=[next(n for n in bodies if m.body(m.jnt_bodyid[m.actuator_trnid[a,0]]).name.endswith(n)) for a in self.motors]
        self.upper=np.array([n in ('torso','head','right_upper_arm','right_lower_arm','right_hand','left_upper_arm','left_lower_arm','left_hand') for n in self.names])
        assert self.upper.sum()==20
        self.dofs=np.array([m.jnt_dofadr[m.actuator_trnid[a,0]]+(int(np.argmax(abs(m.actuator_gear[a,:3]))) if m.jnt_type[m.actuator_trnid[a,0]]==1 else 0) for a in self.motors])
        self.original=copy.copy(m)
        self.trace=[]
    def _build_dof_force_tensors(self):self._dof_forces=torch.zeros((1,34))
    def _build_graphs(self):self._graph=None
    def step(self):
        s=self._solver;m=s.mj_model;d=s.mj_data;state=self._sim_state.raw_state
        self._sim_state.pre_step_update()
        s._update_mjc_data(d,self._sim_model,state)
        for a,r in self.balls:d.qpos[a:a+4]=np.roll((r*R.from_quat(np.roll(d.qpos[a:a+4],-1))).as_quat(),1)
        s._apply_mjc_control(self._sim_model,state,self._controls.control,d)
        for _ in range(8):
            mujoco.mj_step(m,d)
            self.trace.append(dict(force=d.qfrc_actuator[self.dofs].copy(),
                command=d.ctrl[self.motors].copy(),velocity=d.actuator_velocity[self.motors].copy(),
                qpos=d.qpos.copy(),qvel=d.qvel.copy()))
        original=d.qpos.copy()
        for a,r in self.balls:d.qpos[a:a+4]=np.roll((r.inv()*R.from_quat(np.roll(d.qpos[a:a+4],-1))).as_quat(),1)
        s._update_newton_state(self._sim_model,state,d,state)
        d.qpos[:]=original
        self._sim_state.post_step_update()
        self._dof_forces[:]=torch.from_numpy(d.actuator_force[self.motors].copy())
        self._sim_step_count+=1
    def profile(self,gain,torque):
        m=self._solver.mj_model;o=self.original
        for key in ('actuator_gainprm','actuator_biasprm','actuator_forcerange','jnt_actfrcrange'):
            getattr(m,key)[:]=getattr(o,key)
        for a in self.motors[self.upper]:
            m.actuator_gainprm[a,0]*=gain;m.actuator_biasprm[a,2]*=gain
            if m.actuator_forcelimited[a]:m.actuator_forcerange[a]*=torque
            else:m.jnt_actfrcrange[m.actuator_trnid[a,0]]*=torque


class CpuEnv(RecoveryOmniEnv):
    def _build_engine(self,config,*args,**kwargs):return CpuEngine(config,*args,**kwargs)


def setup():
    torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cpu')
    mp_util.init(0,1,'cpu',6779)
    SOURCE.mkdir(exist_ok=True)
    with zipfile.ZipFile(ROOT/'Saved/MimicKitEquipment/native-getup-source.zip') as z:
        for name in z.namelist():
            if name.startswith(('assets/','motions/','prepared/')):
                p=SOURCE/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
    for p in (SOURCE/'prepared').glob('*.yaml'):
        p.write_text(p.read_text().replace('/workspace/mimickit_trial',SOURCE.as_posix()))
    cfg,ec,ac=[yaml.safe_load((SOURCE/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
    cfg['char_file']=cfg['char_file'].replace('/workspace/mimickit_trial',SOURCE.as_posix())
    original=omni_walk.row_motion_weights
    omni_walk.row_motion_weights=lambda g,w,f,n:(1,original(g,w,f,2)[1])
    env=CpuEnv(cfg,ec,1,'cpu',False)
    agent=OmniPPOAgent(ac,env,'cpu')
    with zipfile.ZipFile(OUT/'checkpoint.zip') as z:agent.load_state_dict(torch.load(io.BytesIO(z.read('model.pt')),map_location='cpu',weights_only=True))
    agent.eval();agent.set_mode(AgentMode.TEST);env.set_mode(EnvMode.TEST)
    return env,agent


def run():
    env,agent=setup();e=env._engine;m=e._solver.mj_model;started=time.time()
    mujoco.mj_saveModel(m,str(OUT/'model.mjb'),None)
    rows=[];captures={}
    for motion in (0,1):
        for tag,gain,torque in [('current',1,1),('torque2',1,2),('gain2',2,1),('both2',2,2),('both4',4,4)]:
            e.profile(gain,torque)
            # Same RNG / physical initialization / solver state for each profile.
            mujoco.mj_resetData(m,e._solver.mj_data)
            torch.manual_seed(81+motion)
            for attempt in range(20):
                obs,info=env.reset()
                if int(env._recovery_motion[0])==motion:break
            assert int(env._recovery_motion[0])==motion
            e.trace=[];poses=[];errors=[];loss=[];first_failure=None
            horizon=int(round(float(env._recovery_lib.get_motion_length(motion))*30))
            for tick in range(horizon):
                with torch.no_grad():action,_=agent._decide_action(obs,info);obs,reward,done,info=env.step(action)
                pos=e.get_body_pos(0)[0].numpy().copy();poses.append(pos)
                error=float((e.get_body_pos(0)-env.reward_target_pos).norm(dim=-1).max())
                errors.append(error);loss.append(float(env.loss_terms.sum()))
                if int(done[0])==1 and first_failure is None:first_failure=tick+1
                if not np.isfinite(pos).all():raise RuntimeError('Nonfinite diagnostic')
            force=np.array([v['force'] for v in e.trace]);caps=e._uefn_motors.upper.numpy();ratio=abs(force)/caps
            poses=np.array(poses);key=f'{motion}_{tag}'
            captures[key+'_pose']=poses;captures[key+'_force']=force
            captures[key+'_qpos']=np.array([v['qpos'] for v in e.trace]);captures[key+'_qvel']=np.array([v['qvel'] for v in e.trace]);captures[key+'_ctrl']=np.array([v['command'] for v in e.trace])
            rows.append(dict(motion=motion,profile=tag,first_failure_tick=first_failure,horizon=horizon,
                max_head_height=float(poses[:,2,2].max()),max_pelvis_height=float(poses[:,0,2].max()),
                final_head_height=float(poses[-1,2,2]),mean_body_error_m=float(np.mean(errors)),
                mean_loss=float(np.mean(loss)),peak_torque_nm=abs(force).max(0).tolist(),
                original_cap_duty=(ratio>=.99).mean(0).tolist()))
            print(json.dumps({k:v for k,v in rows[-1].items() if k not in ('peak_torque_nm','original_cap_duty')}),flush=True)
    report=dict(rows=rows,motor_names=e.names,caps_nm=e._uefn_motors.upper.numpy().tolist(),seconds=time.time()-started,
        backend='MuJoCo CPU, same compiled native configuration; not GPU trajectory identity',
        continuation='No automatic reset after first failure, for diagnosis only')
    (OUT/'strength.json').write_text(json.dumps(report,indent=2));np.savez_compressed(OUT/'strength-traces.npz',**captures)

if __name__=='__main__':run()
