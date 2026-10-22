"""Single-agent CPU inference using the pinned locomotion policy and native physics."""
import os,sys,json,io,zipfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitIdleLive';SOURCE=OUT/'source'
os.environ['PYGLET_HEADLESS']='true'
os.environ['OMP_NUM_THREADS']='1'
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),str(SOURCE/'pipeline'),str(SOURCE/'MimicKit/mimickit')]
import numpy as np
import torch,warp as wp,newton,mujoco,yaml
from scipy.spatial.transform import Rotation as R
from types import SimpleNamespace
from engines.newton_engine import NewtonEngine
from native_uefn_engine import configure_native_model
from torque_envelope import apply_torque_envelope
import omni_walk
from omni_policy import OmniPPOAgent
from learning.base_agent import AgentMode
from envs.base_env import EnvMode
from util import mp_util

def velocity_kick(model,data,body,direction,strength):
    """Impulse at body COM normalized by articulated effective mass, no teleport."""
    direction=np.asarray(direction,dtype=float);direction/=np.linalg.norm(direction)
    mujoco.mj_forward(model,data)
    jac=np.zeros((3,model.nv));mujoco.mj_jacBodyCom(model,data,jac,None,body)
    gradient=direction@jac
    inverse=np.zeros((1,model.nv))
    mujoco.mj_solveM(model,data,inverse,gradient[None].copy())
    mobility=float(gradient@inverse[0])
    if mobility<=1e-12:raise ValueError('Selected body cannot move in this direction')
    impulse=float(strength)/mobility
    before=jac@data.qvel
    data.qvel+=inverse[0]*impulse
    measured=float(direction@(jac@data.qvel-before))
    return dict(requested_m_s=float(strength),measured_m_s=measured,impulse_ns=impulse,body_mass_kg=float(model.body_mass[body]))

class CpuEngine(NewtonEngine):
    def __init__(self,config,*args,**kwargs):
        self.config=config;self.pending_kick=None;self.last_kick=None
        super().__init__(config,*args,**kwargs)
    def _build_solver(self):
        apply_torque_envelope(self._sim_model,self.config['uefn_motor_torque_caps_nm'])
        self._sim_model.joint_armature.zero_()
        self._solver=newton.solvers.SolverMuJoCo(self._sim_model,use_mujoco_cpu=True,
            solver='newton',njmax=450,nconmax=150,impratio=10,iterations=100,ls_iterations=50)
        m=self._solver.mj_model
        meta=json.loads((Path(self.config['uefn_asset_directory'])/'limits.json').read_text())
        refs,_=configure_native_model(m,meta)
        self.balls=[(int(m.jnt_qposadr[j]),R.from_quat(refs[j])) for j in range(m.njnt) if m.jnt_type[j]==1]
        motors=np.flatnonzero(m.actuator_biasprm[:,2]!=0)
        gains=-m.actuator_biasprm[motors,2]
        caps=np.array([m.actuator_forcerange[a,1] if m.actuator_forcelimited[a] else m.jnt_actfrcrange[m.actuator_trnid[a,0],1] for a in motors])
        self._uefn_motors=SimpleNamespace(gains=wp.array(gains.astype(np.float32),device='cpu'),upper=wp.array(caps.astype(np.float32),device='cpu'))
    def _build_dof_force_tensors(self):self._dof_forces=[torch.zeros((1,34))]
    def _build_graphs(self):self._graph=None
    def _to_native(self):
        s=self._solver;d=s.mj_data;state=self._sim_state.raw_state
        self._sim_state.pre_step_update();s._update_mjc_data(d,self._sim_model,state)
        for a,r in self.balls:d.qpos[a:a+4]=np.roll((r*R.from_quat(np.roll(d.qpos[a:a+4],-1))).as_quat(),1)
        return d
    def step(self):
        s=self._solver;m=s.mj_model;d=self._to_native();state=self._sim_state.raw_state
        if self.pending_kick:
            body,direction,strength=self.pending_kick
            self.last_kick=velocity_kick(m,d,body,direction,strength);self.pending_kick=None
        s._apply_mjc_control(self._sim_model,state,self._controls.control,d)
        for _ in range(8):mujoco.mj_step(m,d)
        mujoco.mj_forward(m,d)
        original=d.qpos.copy()
        for a,r in self.balls:d.qpos[a:a+4]=np.roll((r.inv()*R.from_quat(np.roll(d.qpos[a:a+4],-1))).as_quat(),1)
        s._update_newton_state(self._sim_model,state,d,state)
        d.qpos[:]=original
        self._sim_state.post_step_update();self._sim_step_count+=1
    def refresh_body_velocities(self):pass

class IdleEnv(omni_walk.OmniWalkEnv):
    def _build_engine(self,config,*args,**kwargs):return CpuEngine(config,*args,**kwargs)
    def _command_phase(self,env_ids=None,dt=0.):
        if not hasattr(self,'live_phase'):return super()._command_phase(env_ids,dt)
        ids=self._motion_ids if env_ids is None else self._motion_ids[env_ids]
        return ids,self.live_phase if env_ids is None else self.live_phase[env_ids]

class Simulation:
    def __init__(self):
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        wp.init();wp.set_device('cpu');mp_util.init(0,1,'cpu',6783)
        cfg,ec,ac=[yaml.safe_load((SOURCE/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
        original=omni_walk.row_motion_weights
        omni_walk.row_motion_weights=lambda g,w,f,n:(1,original(g,w,1.,2)[1])
        cfg['rand_reset']=False;cfg['idle_row_fraction']=1.;cfg['adaptive_motion_rows']=None
        self.env=IdleEnv(cfg,ec,1,'cpu',False)
        self.agent=OmniPPOAgent(ac,self.env,'cpu')
        with zipfile.ZipFile(OUT/'checkpoint.zip') as z:
            self.agent.load_state_dict(torch.load(io.BytesIO(z.read('model.pt')),map_location='cpu',weights_only=True))
        self.agent.eval();self.agent.set_mode(AgentMode.TEST);self.env.set_mode(EnvMode.TEST)
        self.names=list(self.env._engine.get_obj_body_names(0));self.engine=self.env._engine
        self.m=self.engine._solver.mj_model
        self.body_ids=[next(i for i in range(1,self.m.nbody) if self.m.body(i).name.endswith(name)) for name in self.names]
        self.idles={bool(self.env._equipment[i]):i for i in range(len(self.env._gaits)) if self.env._gaits[i]==-1}
        self.tick_count=0;self.compute_ms=0.;self.reset(False)
    def reset(self,drawn=False):
        e=self.env;m=self.idles[bool(drawn)];self.drawn=bool(drawn)
        mujoco.mj_resetData(self.m,self.engine._solver.mj_data)
        e._fixed_motion_ids[:]=m;e._rand_reset=False
        e.live_phase=torch.tensor([[1.,0.]])
        e.reset();self.tick_count=0;self.engine.pending_kick=None;self.engine.last_kick=None
    def kick(self,body,direction,strength):
        if body not in self.names:raise ValueError('Unknown limb')
        strength=float(strength);vec=np.asarray(direction,dtype=float)
        if not np.isfinite(strength) or not 0<strength<=10 or vec.shape!=(3,) or not np.isfinite(vec).all() or np.linalg.norm(vec)<1e-6:raise ValueError('Invalid impulse')
        self.engine.pending_kick=(self.body_ids[self.names.index(body)],vec.tolist(),strength)
    def tick(self):
        start=time.perf_counter();e=self.env;a=self.agent
        with torch.inference_mode():
            obs=e._compute_obs();normalized=a._obs_norm.normalize(obs)
            action=a._a_norm.unnormalize(a._model.eval_actor(normalized).mode)
            phase=a._model.eval_phase(normalized)
            # Training converts prediction through atan2 and back to a unit phase.
            angle=torch.atan2(phase[:,1],phase[:,0]);phase=torch.stack((angle.cos(),angle.sin()),-1)
            e._apply_action(action);self.engine.step();e._time_buf.add_(1/30);e.live_phase=phase
        self.tick_count+=1;self.compute_ms=(time.perf_counter()-start)*1000
        if not np.isfinite(self.engine.get_body_pos(0).numpy()).all():raise RuntimeError('Nonfinite simulation; reset to idle')
    def state(self):
        e=self.engine
        pose=torch.cat((e.get_body_pos(0)[0],e.get_body_rot(0)[0]),-1).tolist()
        return dict(pose=pose,tick=self.tick_count,seconds=self.tick_count/30,compute_ms=self.compute_ms,drawn=self.drawn,last_kick=e.last_kick,phase=self.env.live_phase[0].tolist())
    def geometry(self):
        # Render the actual configured MuJoCo shapes in each body's original frame.
        import xml.etree.ElementTree as ET
        tree=ET.parse(SOURCE/'assets/uefn/humanoid_uefn.xml')
        bodies=[]
        for name in self.names:
            b=tree.find(f".//body[@name='{name}']")
            bodies.append(dict(name=name,shapes=[dict(type=g.get('type','sphere'),size=list(map(float,g.get('size').split())),pos=list(map(float,g.get('pos','0 0 0').split())),quat=list(map(float,g.get('quat','1 0 0 0').split()))) for g in b.findall('geom')]))
        return dict(bodies=bodies,checkpoint=json.loads((OUT/'checkpoint.json').read_text()),physics_hz=240,policy_hz=30)

if __name__=='__main__':
    s=Simulation();print('INITIAL',s.state(),flush=True)
    times=[]
    for i in range(90):
        if i==30:s.kick('right_hand',[0,1,0],1.)
        s.tick();times.append(s.compute_ms)
    print('RESULT',json.dumps(dict(state=s.state(),mean_ms=float(np.mean(times[5:])))),flush=True)
