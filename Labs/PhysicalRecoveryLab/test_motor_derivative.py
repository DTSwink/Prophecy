"""Compare optimized motor derivative to the untouched generic calculation."""
import json
import numpy as np
import torch
import warp as wp
from mujoco_warp._src import derivative,forward
from recovery_env import RecoveryEnv,OUT
from motor_derivative import DiagonalMotorDerivative


def main():
    torch.set_num_threads(1);torch.manual_seed(991);wp.init()
    env=RecoveryEnv(128,auto_reset=False,native_motors=True,relative_targets=True,integrator='implicitfast')
    m=env.sim.wp_model;d=env.sim.wp_data;extension=m.prophecy_motor_derivative
    q=env.qpos.clone();v=torch.randn_like(env.qvel)*5;actions=torch.randn_like(env.controller.actions)*2
    env.qvel.copy_(v);env.controller.actions.copy_(actions)
    wp.capture_launch(env.sim.forward_graph)
    generic=wp.zeros_like(d.qM);fast=wp.zeros_like(d.qM)
    m.prophecy_motor_derivative=None;derivative.deriv_smooth_vel(m,d,generic)
    m.prophecy_motor_derivative=extension;derivative.deriv_smooth_vel(m,d,fast)
    difference=float(abs(generic.numpy()-fast.numpy()).max());assert difference==0,difference
    # Isolate the modified integration calculation from a second, unordered
    # contact solve. Both paths consume exactly the same solved acceleration.
    initial_q=env.qpos.clone();initial_v=env.qvel.clone();integrated=[]
    for implementation in (None,extension,None):
        m.prophecy_motor_derivative=implementation
        env.qpos.copy_(initial_q);env.qvel.copy_(initial_v)
        forward.implicit(m,d)
        integrated.append((env.qpos.cpu().numpy().copy(),env.qvel.cpu().numpy().copy()))
    iq=float(abs(integrated[0][0]-integrated[1][0]).max())
    iv=float(abs(integrated[0][1]-integrated[1][1]).max())
    repeat_iq=float(abs(integrated[0][0]-integrated[2][0]).max())
    repeat_iv=float(abs(integrated[0][1]-integrated[2][1]).max())
    assert all(np.isfinite(a).all() for pair in integrated for a in pair)
    outputs=[]
    for implementation in (None,extension,None):
        m.prophecy_motor_derivative=implementation;env.sim.create_graph()
        env.reset(torch.ones(env.num_envs,device='cuda',dtype=torch.bool))
        env.qpos.copy_(q);env.qvel.copy_(v);env.controller.actions.copy_(actions)
        wp.capture_launch(env.sim.step_graph)
        outputs.append((env.qpos.cpu().numpy().copy(),env.qvel.cpu().numpy().copy()))
    dq=float(abs(outputs[0][0]-outputs[1][0]).max());dv=float(abs(outputs[0][1]-outputs[1][1]).max())
    repeat_dq=float(abs(outputs[0][0]-outputs[2][0]).max())
    repeat_dv=float(abs(outputs[0][1]-outputs[2][1]).max())
    gear=env.sim.mj_model.actuator_gear[0].copy()
    env.sim.mj_model.actuator_gear[0,0]=.5
    rejected=False
    try:DiagonalMotorDerivative(env.sim.mj_model,m)
    except ValueError:rejected=True
    finally:env.sim.mj_model.actuator_gear[0]=gear
    assert rejected,'Must refuse a non-one-hot transmission'
    report={'passed':True,'worlds':env.num_envs,'derivative_max_error':difference,
        'same_solved_state_qpos_error':iq,'same_solved_state_qvel_error':iv,
        'same_solved_state_generic_repeat':{'qpos':repeat_iq,'qvel':repeat_iv},
        'independent_full_steps_generic_vs_optimized':{'qpos':dq,'qvel':dv},
        'independent_full_steps_generic_vs_generic':{'qpos':repeat_dq,'qvel':repeat_dv},
        'scope':'Pass requires bitwise derivative equality and unsupported-gear rejection. Integration deltas and generic repeat variability are reported, not used as a full-trajectory equivalence certificate.',
        'unsupported_gear_rejected':rejected,
        'controller':env.controller.contract,'rig_sha256':env.metadata['rig_sha256']}
    (OUT/'motor-derivative-tests.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
