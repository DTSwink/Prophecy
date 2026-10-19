"""Native MuJoCo parameter calibration against saved, successful Jolt Run LR.

CPU only. No custom solver, force callbacks, projection or Unreal interaction.
Settings are isolated in disposable mjModels; canonical rig is never written.
"""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT'] = str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import argparse, json, time, hashlib
import probe
import mujoco, numpy as np
from scipy.spatial.transform import Rotation as R
import native_probe as policy
from probe_sequential_contacts import encode as encode_original, decode

BASE = probe.OUT/'causal_transfer'
OUT = ROOT/'Saved/MimicKitTransfer/vanilla-calibration'
CHECKPOINT = ROOT/'Saved/MimicKitLocal/runs/2026-10-16_02-00_transfer_finetune_512/model.pt'
MODEL = BASE/'sequential_model.mjb'
REFERENCE = BASE/'local_finetune4013_phases16.npz'
NATIVE = BASE/'local_finetune4013_phases16_self0_native_v40p8_point.npz'


def encode(m,state):
    q,v=encode_original(m,state)
    # Re-centering a native ball joint changes coordinates, not physical pose.
    # Observation and motor axes remain the original child-body axes.
    rot=R.from_quat(state[:,3:7])
    for i,name in enumerate(policy.names[1:],1):
        b=next(b for b in range(1,m.nbody) if m.body(b).name.endswith(name))
        j=m.body_jntadr[b]
        if m.jnt_type[j]==mujoco.mjtJoint.mjJNT_BALL:
            qa=m.jnt_qposadr[j]
            rest=R.from_quat(np.roll(m.body_quat[b],-1))
            q[qa:qa+4]=np.roll((rest.inv()*rot[policy.parents[i]].inv()*rot[i]).as_quat(),1)
    return q,v


def load():
    policy.load_actor(CHECKPOINT)
    with np.load(REFERENCE) as z: ref = {k:z[k] for k in z.files}
    with np.load(NATIVE) as z: native = {k:z[k] for k in z.files}
    return ref, native


def build(settings):
    if settings.get('hz',240)!=240:
        raise ValueError('User requires fixed240Hz physics and30Hz policy; frequency changes are excluded.')
    m = mujoco.MjModel.from_binary_path(str(MODEL))
    m.opt.timestep = 1/settings.get('hz',240)
    m.opt.integrator = getattr(mujoco.mjtIntegrator, 'mjINT_'+settings.get('integrator','IMPLICITFAST'))
    m.opt.solver = getattr(mujoco.mjtSolver, 'mjSOL_'+settings.get('solver','NEWTON'))
    m.opt.cone = getattr(mujoco.mjtCone, 'mjCONE_'+settings.get('cone','PYRAMIDAL'))
    m.opt.iterations = settings.get('iterations',100)
    m.opt.ls_iterations = settings.get('ls_iterations',50)
    m.opt.tolerance = settings.get('tolerance',1e-8)
    m.opt.impratio = settings.get('impratio',10)
    m.opt.disableflags = 0
    # Keep archived masses/inertia, caps, geometry and existing native hinge limits.
    # Binary has no native ball limits: recorded explicitly, not called PHAT parity.
    m.dof_armature[:] = 0
    motors = np.flatnonzero(m.actuator_biasprm[:,2] != 0)
    assert len(motors)==34
    # Newton caps ball motors individually and scalar hinges at the joint.
    for motor in motors:
        joint=m.actuator_trnid[motor,0]
        assert m.actuator_forcelimited[motor] or m.jnt_actfrclimited[joint]
    gain = settings.get('gain',1.)
    m.actuator_gainprm[motors,0] *= gain
    m.actuator_biasprm[motors,2] *= gain
    if settings.get('contact_profile',False):
        floor = np.flatnonzero(m.geom_bodyid==0)
        m.geom_condim[:] = 1  # frictionless self contacts, still colliding
        m.geom_priority[:] = 0
        m.geom_condim[floor] = settings.get('condim',3)
        m.geom_priority[floor] = 1
        m.geom_friction[floor] = [settings.get('friction',1.), settings.get('torsion',.005), .0001]
    if 'solref' in settings: m.geom_solref[:] = settings['solref']
    if 'solimp' in settings: m.geom_solimp[:] = settings['solimp']
    if 'margin' in settings: m.geom_margin[:] = settings['margin']/2
    if 'limit_solref' in settings: m.jnt_solref[:] = settings['limit_solref']
    if 'limit_solimp' in settings: m.jnt_solimp[:] = settings['limit_solimp']
    if 'ball_limit' in settings:
        # Diagnostic spherical approximations, explicitly NOT exact PHAT bounds.
        meta=json.loads((probe.SOURCE/'assets/uefn/limits.json').read_text())
        for j in meta['joints']:
            if j['kind']!='ball':continue
            b=next(i for i in range(1,m.nbody) if m.body(i).name.endswith(j['body']))
            idx=m.body_jntadr[b]
            angles=np.asarray(j['limits_rad'])
            center=R.from_quat(np.roll(j['reference_wxyz'],-1))
            reference=center.magnitude()
            if settings.get('center_ball_limits',False):
                oldrest=R.from_quat(np.roll(m.body_quat[b],-1))
                m.body_quat[b]=np.roll((oldrest*center.inv()).as_quat(),1)
                qa=m.jnt_qposadr[idx];m.qpos0[qa:qa+4]=j['reference_wxyz']
                reference=0.
            mode=settings['ball_limit']
            if mode=='max':radius=reference+max(angles)
            elif mode=='combined':radius=reference+np.hypot(angles[0],max(angles[1:]))
            else:raise ValueError(mode)
            m.jnt_limited[idx]=True;m.jnt_range[idx]=[0,radius*settings.get('ball_scale',1.)]
    if settings.get('no_limits',False): m.opt.disableflags |= int(mujoco.mjtDisableBit.mjDSBL_LIMIT)
    if 'armature' in settings: m.dof_armature[6:] = settings['armature']
    if 'damping' in settings: m.dof_damping[6:] = settings['damping']
    if settings.get('per_actuator_caps',False):
        for motor in motors:
            joint=m.actuator_trnid[motor,0]
            if m.jnt_actfrclimited[joint]:
                m.actuator_forcerange[motor]=m.jnt_actfrcrange[joint]
                m.actuator_forcelimited[motor]=True
                m.jnt_actfrclimited[joint]=False
    return m,motors


def advance(m,d,motors,command):
    d.ctrl[motors] = np.clip(command,-2*np.pi,2*np.pi)
    # Native integration only. Policy holds its command for exactly 1/30 second.
    for _ in range(round(1/(30*m.opt.timestep))): mujoco.mj_step(m,d)
    return decode(m,d)


def validate(ref,native):
    m,_ = build({});d=mujoco.MjData(m)
    rows=[]
    for world in range(16):
        initial=ref['initial'][world]
        d.qpos[:],d.qvel[:]=encode(m,initial)
        mapped=decode(m,d)
        obs=policy.observation(mapped,ref['obs'][0,world,-5:])
        error=float(np.max(np.abs(obs-ref['obs'][0,world])))
        action_error=float(np.max(np.abs(policy.actor(obs)-ref['actions'][0,world])))
        rows.append(dict(world=world,obs_error=error,action_error=action_error,
                         position_error=float(np.max(np.abs(mapped[:,:3]-initial[:,:3])))))
    assert max(r['obs_error'] for r in rows)<1e-3,rows
    assert max(r['action_error'] for r in rows)<2e-3,rows
    return dict(mapping=rows,mujoco=mujoco.__version__,checkpoint_sha256=hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest(),
                model_sha256=hashlib.sha256(MODEL.read_bytes()).hexdigest(),
                ball_joint_limits='Absent in upstream Newton ball conversion; native ball cone cannot exactly express PHAT swing/twist',
                native_reference=str(NATIVE),reference=str(REFERENCE),
                native_reference_ticks=[len(native['world'+str(w)])-1 for w in range(16)])


def one_tick(settings,native,worlds=range(0,16,2),ticks=(0,8,24,80,160,240)):
    m,motors=build(settings);d=mujoco.MjData(m);rows=[]
    for world in worlds:
        for tick in ticks:
            state=native['world'+str(world)][tick]
            target=native['world'+str(world)][tick+1]
            mujoco.mj_resetData(m,d);d.qpos[:],d.qvel[:]=encode(m,state)
            start=decode(m,d)
            actual=advance(m,d,motors,native['actions'+str(world)][tick])
            angle=(R.from_quat(actual[:,3:7]).inv()*R.from_quat(target[:,3:7])).magnitude()
            rows.append(dict(world=world,tick=tick,
                pos_rms=float(np.sqrt(np.mean((actual[:,:3]-target[:,:3])**2))),
                angle_rms=float(np.sqrt(np.mean(angle**2))),
                linvel_rms=float(np.sqrt(np.mean((actual[:,7:10]-target[:,7:10])**2))),
                angvel_rms=float(np.sqrt(np.mean((actual[:,10:13]-target[:,10:13])**2))),
                projection_m=float(np.max(np.linalg.norm(start[:,:3]-state[:,:3],axis=1))),
                peak_speed=float(np.max(np.abs(actual[:,7:])))))
    return {k:float(np.mean([r[k] for r in rows])) for k in ('pos_rms','angle_rms','linvel_rms','angvel_rms','projection_m')} | {'rows':rows}


def rollout(settings,ref,worlds=(0,4,8,12),save=False):
    m,motors=build(settings);d=mujoco.MjData(m);rows=[];captures={}
    for world in worlds:
        mujoco.mj_resetData(m,d);d.qpos[:],d.qvel[:]=encode(m,ref['initial'][world])
        current=decode(m,d);history=[current];distances=[];peak_penetration=0.;max_speed=0.;solver_counts=[]
        for tick in range(300):
            command=policy.actor(policy.observation(current,ref['obs'][tick,world,-5:]))
            current=advance(m,d,motors,command)
            target=ref['targets'][tick,world].copy();target[:,:2]+=current[0,:2]-target[0,:2]
            actual_c=current[policy.keys,:3]+R.from_quat(current[policy.keys,3:7]).apply(policy.offsets)
            target_c=target[policy.keys,:3]+R.from_quat(target[policy.keys,3:7]).apply(policy.offsets)
            distance=np.linalg.norm(actual_c-target_c,axis=1)
            distances.append(float(distance.max()));history.append(current.copy())
            for c in d.contact:
                if m.geom_bodyid[c.geom1]==0 or m.geom_bodyid[c.geom2]==0:
                    peak_penetration=max(peak_penetration,float(-c.dist))
            max_speed=max(max_speed,float(abs(current[:,10:13]).max()))
            solver_counts.append(int(d.solver_niter.max()))
            if not np.isfinite(current).all() or distances[-1]>.27:break
        rows.append(dict(world=world,ticks=len(distances),seconds=len(distances)/30,
                         passed=len(distances)==300 and distances[-1]<=.27,
                         peak_target_m=max(distances),floor_penetration_m=peak_penetration,
                         peak_angular_velocity=max_speed,mean_solver_iterations=float(np.mean(solver_counts))))
        if save:captures['world'+str(world)]=history
    return dict(passes=sum(r['passed'] for r in rows),mean_seconds=float(np.mean([r['seconds'] for r in rows])),rows=rows),captures


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--settings',type=Path);ap.add_argument('--name',default='screen');ap.add_argument('--full',action='store_true');ap.add_argument('--one-tick-only',action='store_true');ap.add_argument('--worlds',type=int,nargs='+');a=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    ref,native=load();validation=validate(ref,native)
    (OUT/'validation.json').write_text(json.dumps(validation,indent=2))
    if a.settings:
        candidates=json.loads(a.settings.read_text())
    else:
        profile=dict(contact_profile=True,cone='ELLIPTIC')
        candidates={
            'upstream240':{},
            'material240':profile,
            'hard240':profile|dict(solref=[1/120,1],solimp=[.99,.99,.001,.5,2]),
        }
    results={}
    for name,settings in candidates.items():
        start=time.perf_counter();one=one_tick(settings,native)
        result=dict(settings=settings,one_tick=one)
        if not a.one_tick_only:
            result['rollout'],capture=rollout(settings,ref,a.worlds if a.worlds else (range(16) if a.full else (0,4,8,12)),save=a.full)
            if a.full:np.savez_compressed(OUT/(a.name+'_'+name+'.npz'),**capture)
        result['elapsed_seconds']=time.perf_counter()-start;results[name]=result
        (OUT/(a.name+'.json')).write_text(json.dumps(results,indent=2))
        print(json.dumps(dict(name=name,one_tick={k:v for k,v in one.items() if k!='rows'},rollout=result.get('rollout'),elapsed=result['elapsed_seconds'])),flush=True)

if __name__=='__main__':main()
