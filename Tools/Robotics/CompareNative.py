"""Frozen CPU MuJoCo control for the same two transition trials as Unreal.

Builds the frozen native recovery model (identical locomotion rig/config),
using the existing CPU engine. Runs one CPU thread and writes a compact receipt.
"""
from pathlib import Path
import os, sys, json, types
ROOT = Path(__file__).resolve().parents[2]
os.environ['OMP_NUM_THREADS'] = '1'
sys.path[:0] = [str(ROOT/'Saved/MimicKitUEFN/dependencies'), str(ROOT/'Saved/SlashPythonDependencies')]
import numpy as np
import mujoco
import onnxruntime as ort
from scipy.spatial.transform import Rotation as R

transfer = types.ModuleType('transfer')
source = ROOT/'Labs/MimicKitTransfer/getup_transfer.py'
transfer.__file__ = str(source)
exec(compile(source.read_text().split('class Policy:')[0].replace('from omni_policy import OmniPPOModel',''), str(source), 'exec'), transfer.__dict__)
folder = ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023'
from engines.newton_engine import NewtonEngine
from engines.engine import ObjType
from native_uefn_engine import configure_native_model
from torque_envelope import apply_torque_envelope
from types import SimpleNamespace
import warp as wp, newton
import torch, yaml
from util import mp_util
cpu_source = (ROOT/'Labs/MimicKitIdleLive/simulation.py').read_text()
exec(cpu_source[cpu_source.index('class CpuEngine('):cpu_source.index('class IdleEnv(')])
wp.init(); wp.set_device('cpu'); mp_util.init(0,1,'cpu',6783)
config = yaml.safe_load((ROOT/'Saved/MimicKitLocomotion/unreal-handoff-20261026/engine_config.yaml').read_text())
config['uefn_asset_directory'] = str(transfer.ASSET)
engine = CpuEngine(config,1,'cpu',False)
env = engine.create_env()
engine.create_obj(env,ObjType.articulated,str(transfer.ASSET/'humanoid_uefn.xml'),'character',enable_self_collisions=True)
engine.initialize_sim()
model = engine._solver.mj_model
assert (model.nbody, model.nq, model.nv) == (16, 51, 40)
assert model.opt.timestep == 1/240
opts = ort.SessionOptions(); opts.intra_op_num_threads = opts.inter_op_num_threads = 1
policies = [ort.InferenceSession(str(ROOT/'Content/locomotion/NN/robots'/name), sess_options=opts, providers=['CPUExecutionProvider'])
            for name in ('getup_161960.onnx', 'clanker_214358.onnx')]
velocity_motors = np.flatnonzero(model.actuator_biasprm[:, 2] != 0)
assert len(velocity_motors) == 34

def read(data):
    states = np.empty((15, 13))
    for i in range(15):
        b = i+1
        jp, jr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
        mujoco.mj_jacBodyCom(model, data, jp, jr, b)
        states[i] = np.r_[data.xpos[b], np.roll(data.xquat[b], -1), jp@data.qvel, jr@data.qvel]
    return states

def reset(state):
    data = mujoco.MjData(model)
    data.qpos[:3] = state[0, :3]; data.qpos[3:7] = np.roll(state[0, 3:7], 1)
    root_rotation = R.from_quat(state[0, 3:7])
    data.qvel[:3] = state[0, 7:10] - np.cross(state[0, 10:13], root_rotation.apply(model.body_ipos[1]))
    data.qvel[3:6] = root_rotation.inv().apply(state[0, 10:13])
    rotations = R.from_quat(state[:, 3:7])
    _, velocities = transfer.joint_state(state)
    data.qvel[6:] = velocities
    for j in range(1, 15):
        b = j+1; parent = model.body_parentid[b]-1; a = model.jnt_qposadr[j]
        q = R.from_quat(np.roll(model.body_quat[b], -1)).inv()*rotations[parent].inv()*rotations[j]
        if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_BALL:
            data.qpos[a:a+4] = np.roll(q.as_quat(), 1)
        else:
            data.qpos[a] = q.as_rotvec()@model.jnt_axis[j]
    mujoco.mj_forward(model, data)
    actual = read(data)
    np.testing.assert_allclose(actual[:, :3], state[:, :3], atol=2e-5, rtol=0)
    np.testing.assert_allclose(actual[:, 7:], state[:, 7:], atol=1e-3, rtol=0)
    return data

def main():
    z = np.load(folder/'native-native-baseline-4.npz')
    results = []
    for case, lane in enumerate((0, 3)):
        data = reset(z['states'][0, lane]); phase = z['phase'][0, lane].copy()
        states, phases, actions = [], [], []
        for tick in range(720):
            state = read(data); states.append(state); phases.append(phase.copy())
            obs = transfer.observation(state, {'sword_drawn':False, 'arm_enabled':[1,1]}, phase).numpy()
            obs[0,146] = -1 if tick<420 else 0 if tick<570 else 1
            obs[0,147:149] = [1,0] if case==0 or tick<420 else [0,1]
            action, following = policies[int(tick>=300)].run(None, {'observations':obs})
            actions.append(action[0]); data.ctrl[:] = 0; data.ctrl[velocity_motors] = action[0]
            for _ in range(8): mujoco.mj_step(model, data)
            mujoco.mj_forward(model, data); phase = following[0]
        states = np.asarray(states)
        result = dict(case=case, getup_height_cm=float(states[299,0,2]*100),
                      idle_min_cm=float(states[300:420,0,2].min()*100), moving_min_cm=float(states[420:,0,2].min()*100),
                      walk_min_cm=float(states[420:570,0,2].min()*100),run_min_cm=float(states[570:,0,2].min()*100),
                      first_fall_tick=next((t for t in range(420,720) if states[t,0,2]<.6),None),
                      walk_cm=float(np.linalg.norm(states[570,0,:2]-states[420,0,:2])*100),
                      run_cm=float(np.linalg.norm(states[719,0,:2]-states[570,0,:2])*100))
        results.append(result); print(json.dumps(result), flush=True)
        np.savez_compressed(ROOT/f'Saved/Diagnostics/RobotLocomotion20261026/native-case{case}.npz',
                            states=states, phases=phases, actions=actions)
    out = ROOT/'Saved/Diagnostics/RobotLocomotion20261026/native-mujoco-control.json'
    out.write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
