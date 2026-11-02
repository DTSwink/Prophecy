"""Package the accepted pelvismax recovery checkpoint; never starts simulation."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import numpy as np
import torch
import onnxruntime as ort
import getup_transfer as g

DEST = g.ROOT / 'Exports/MimicKitEquipment/Recovery_Pelvismax161960_Unreal_20261026'
CHECKPOINT = g.ROOT / 'Saved/MimicKitEquipment/preserved-latest/20261022_131128_uefn_getup_pelvismax7_1024/checkpoint_0161960_final.zip'
EXPECTED = '0dc58150f87f1cb25816235f9e565638e9972d262b9203c5da0d14c0ea736a2b'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Actor(torch.nn.Module):
    def __init__(self, policy):
        super().__init__()
        self.layers = policy.model._actor_layers
        self.motor = policy.model._action_dist._mean_net
        self.phase = policy.model._phase_out
        for name, key in [('obs_mean', '_obs_norm._mean'), ('obs_std', '_obs_norm._std'),
                          ('action_mean', '_a_norm._mean'), ('action_std', '_a_norm._std')]:
            self.register_buffer(name, policy.saved[key])
        self.register_buffer('bounds', policy.bound)

    def forward(self, observations):
        hidden = self.layers(((observations-self.obs_mean)/self.obs_std).clamp(-10., 10.))
        action = (self.motor(hidden)*self.action_std+self.action_mean).clamp(-self.bounds, self.bounds)
        return action, torch.nn.functional.normalize(self.phase(hidden), dim=-1, eps=1e-6)


def main():
    assert sha(CHECKPOINT) == EXPECTED, 'Unexpected checkpoint'
    assert not (DEST/'manifest.json').exists(), 'Preserve completed package'
    if DEST.exists():
        assert sha(DEST/CHECKPOINT.name) == EXPECTED, 'Unexpected partial package'
    with zipfile.ZipFile(CHECKPOINT) as archive:
        assert archive.testzip() is None
        model_name = next(n for n in archive.namelist() if Path(n).name == 'model.pt')
        assert hashlib.sha256(archive.read(model_name)).hexdigest() == sha(g.OUT/'native/model.pt')
    DEST.mkdir(parents=True, exist_ok=True)

    def copy(source, relative):
        target = DEST/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        assert sha(source) == sha(target)

    copy(CHECKPOINT, 'checkpoint_0161960_final.zip')
    for name in ('model.pt', 'agent_config.yaml', 'env_config.yaml', 'engine_config.yaml',
                 'velocity_command_bounds.json', 'torque_envelope.json', 'provenance.json', 'runtime-freeze.txt'):
        copy(g.OUT/'native'/name, 'policy/'+name)
    for name in ('humanoid_uefn.xml', 'physics.json', 'limits.json'):
        copy(g.ASSET/name, 'rig/'+name)
    for name in ('profile.json', 'fixture.cpp', 'jolt-rig-generated.h'):
        copy(g.OUT/'jolt-native-profile'/name, 'jolt/'+name)
    copy(g.ROOT/'Labs/MimicKitTransfer/generated/recovery_fixture.inl', 'reference/recovery_fixture.inl')
    copy(g.ROOT/'Plugins/ProphecyJolt/Source/ProphecyJolt/Private/Tests/ProphecyJoltRecoveryTransferTests.cpp',
         'reference/ProphecyJoltRecoveryTransferTests.cpp')
    for name in ('getup_transfer.py', 'getup_unreal.py', 'build_getup_native_profile.py', 'package_getup_handoff.py'):
        copy(g.ROOT/'Labs/MimicKitTransfer'/name, 'reference/'+name)
    for source, target in [('MimicKit/mimickit/envs/char_env.py', 'char_env.py'),
                           ('MimicKit/mimickit/util/torch_util.py', 'torch_util.py'),
                           ('pipeline/omni_policy.py', 'omni_policy.py')]:
        copy(g.SOURCE/source, 'reference/'+target)
    copy(g.OUT/'fresh-100/summary.json', 'validation/fresh-100-summary.json')

    policy = g.Policy('native')
    wrapper = Actor(policy).eval()
    output = DEST/'policy/recovery_actor.onnx'
    torch.onnx.export(wrapper, torch.zeros(1,154), str(output), dynamo=False, opset_version=17,
        input_names=['observations'], output_names=['joint_velocity_rad_s', 'next_phase'],
        dynamic_axes={n:{0:'batch'} for n in ('observations','joint_velocity_rad_s','next_phase')})
    options = ort.SessionOptions()
    options.intra_op_num_threads = options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(output), sess_options=options, providers=['CPUExecutionProvider'])
    recorded = []
    for index in range(2,20):
        row, states = g.replay('native', index)
        for tick, state in enumerate(states):
            recorded.append(g.observation(state, row, row['frame_phase'][tick][:2]).numpy()[0])
    recorded = np.asarray(recorded, dtype=np.float32)
    errors = np.zeros(2)
    rng = np.random.default_rng(161960)
    cases = [recorded] + [rng.normal(0,100,(n,154)).astype(np.float32) for n in (1,7,64)]
    case_reports=[]
    for case_index,obs in enumerate(cases):
        expected = policy(torch.from_numpy(obs))
        actual = session.run(None, {'observations':obs})
        case_errors=[]
        for i,(a,b) in enumerate(zip(actual,expected)):
            # Extreme synthetic observations saturate normalization. FP32 GEMM
            # accumulation differs across runtimes; real rollouts stay strict.
            tolerance = 3e-5 if case_index == 0 else 1e-3
            np.testing.assert_allclose(a,b,atol=tolerance,rtol=3e-5)
            case_errors.append(float(np.max(np.abs(a-b))))
            errors[i] = max(errors[i], float(np.max(np.abs(a-b))))
        case_reports.append(dict(kind='recorded' if case_index==0 else 'synthetic_std100',
                                 batch=len(obs),max_absolute_errors=case_errors,atol=tolerance,rtol=3e-5))
    actions, phases = policy(torch.from_numpy(recorded[:32]))
    np.savez_compressed(DEST/'validation/inference_vectors.npz', observations=recorded[:32],
                        joint_velocity_rad_s=actions, next_phase=phases)
    report = dict(passed=True, recorded_observations=len(recorded),
                  tested_batches=[len(x) for x in cases], max_absolute_errors=errors.tolist(),cases=case_reports,
                  checkpoint_zip_sha256=EXPECTED, model_sha256=sha(g.OUT/'native/model.pt'),
                  onnx_sha256=sha(output),
                  scope='CPU ONNX Runtime versus frozen PyTorch inference. ONNX not yet run inside Unreal.')
    (DEST/'validation/onnx-parity.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    action_map=[]
    for i,node in enumerate(g.nodes[1:],1):
        for axis in (range(3) if len(node.findall('joint'))==3 else [2]):
            action_map.append(dict(index=len(action_map),body=g.names[i],parent=g.names[g.parents[i]],
                                   child_local_axis='xyz'[axis],bound_rad_s=float(policy.bound[len(action_map)])))
    contract = dict(input={'name':'observations','dtype':'float32','shape':['batch',154],
        'slices':{'0:1':'pelvis body-origin world Z metres', '1:7':'pelvis quaternion to tangent/normal 6D',
        '7:10':'pelvis COM world linear velocity m/s', '10:13':'pelvis world angular velocity rad/s',
        '13:97':'14 joint-relative rotations, tangent/normal 6D each', '97:131':'34 joint velocities, child-local rad/s',
        '131:146':'head, right hand, left hand, right foot, left foot body-origin position minus pelvis origin, world axes',
        '146:154':'[-1, 1, 0, sword_drawn, arm_enabled[0], arm_enabled[1], phase_cos, phase_sin]; both reserved arm inputs are 1 in this checkpoint'}},
        outputs={'joint_velocity_rad_s':['batch',34], 'next_phase':['batch',2]},
        normalization='Embedded frozen observation normalization/clamp, action unnormalization/per-axis bounds and unit phase; do not apply twice',
        coordinates='Training coordinates: Z up, metres, quaternion xyzw. Convert Unreal coordinates consistently with the rig fixture.',
        body_order=g.names, action_map=action_map,
        phase='Use next_phase as phase input on the NEXT policy tick for autoregressive recovery.',
        physics_hz=240, policy_hz=30, exploration_noise=0)
    (DEST/'policy/io-contract.json').write_text(json.dumps(contract,indent=2),encoding='utf-8')
    (DEST/'HANDOFF.md').write_text(HANDOFF,encoding='utf-8')
    manifest = {'run':'20261022_131128_uefn_getup_pelvismax7_1024', 'checkpoint':'161960_final',
        'samples':3668983808, 'selection':'Latest accepted pelvismax checkpoint; later rejected custom runs excluded',
        'files':{str(p.relative_to(DEST)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':sha(p)}
                 for p in sorted(DEST.rglob('*')) if p.is_file()}}
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'folder':str(DEST),'files':len(manifest['files'])+1,'parity':report},indent=2))


HANDOFF = """# Recovery checkpoint → Unreal

Accepted run: **20261022_131128_uefn_getup_pelvismax7_1024**, final checkpoint
**161960**, **3,668,983,808 samples**. This is the latest accepted pelvismax save,
not the later rejected custom-solver fine-tunes. Weights are unchanged.

## Files

- `checkpoint_0161960_final.zip`: complete original checkpoint, including resume state.
- `policy/model.pt`: original PyTorch weights, including frozen normalizers.
- `policy/recovery_actor.onnx`: deterministic actor ready for an ONNX runtime.
- `policy/io-contract.json`: exact input layout, output ordering and units.
- `rig/`: frozen geometry, hierarchy, PHAT export, masses and inertias.
- `jolt/`: tested 32 Hz recovery constraint profile and native fixture implementation.
- `reference/`: observation, phase, motor and Unreal test integration source.
  These are source references from this project, not a standalone build tree;
  their original project-relative imports/includes must be adapted when porting.
- `validation/`: 100-start physical-transfer result, ONNX parity and sample I/O vectors.
- `manifest.json`: every packaged file's SHA256 and size.

## Inference and actuation

Run at **30 Hz**, with **240 Hz physics** (eight substeps per action).
Feed raw float32 `[batch,154]` observations. The ONNX embeds frozen normalization,
clamp ±10, action scaling/per-axis bounds and phase normalization. Do not normalize
again or add exploration noise. Outputs are **34 child-local angular velocity
targets in rad/s**, plus a unit two-component **next-tick phase**. They are not
joint-angle or torque commands. Feed predicted phase back on the next tick.

Use `io-contract.json` and `reference/getup_transfer.py` for exact ordering.
Training space is **Z-up, metres, quaternion xyzw**; Unreal centimetres and
coordinate conversion must be handled consistently. Root linear velocity is
**COM velocity**, whereas key positions are **body origins**. Joint rotations
remove the exported local rest transform. The 6D rotation representation is
defined in `reference/torch_util.py`. Keep equipment/arm condition inputs correct.

Motors use zero stiffness and the original velocity damping gains/torque caps,
with the fixture's conversion to child constraint space. See `jolt/fixture.cpp`,
`jolt/jolt-rig-generated.h`, `policy/torque_envelope.json` and velocity bounds.

## Required Jolt profile

The successful test used the **installed project Jolt DLL inside Unreal**, with
an **opt-in modified recovery rig**. It did not replace the Jolt DLL and did not
switch the existing gameplay rig. Port this rig profile with the policy:

- `native-pelvismax-spherical32`: PHAT-centered total-angle spherical limits on
  ball joints, radius equal to the largest exported angular bound, **32 Hz**,
  critical damping. This is not the original PHAT swing/twist ellipse.
- Original hinge limits; **40 velocity / 8 position iterations**.
- Floor friction **1**, restitution **0**, self-friction **0**.
- Exact fixture contact filtering, mass/inertia, motor caps, no-gyro convention,
  zero native body damping and small explicit compound drag.

Fixture switches: `TRANSFER_NATIVE_BALL_LIMITS=1`,
`TRANSFER_RIG_VELOCITY_STEPS=40`, `TRANSFER_RIG_POSITION_STEPS=8`,
`TRANSFER_TRAINING_CONTACT=1`, `TRANSFER_FRICTIONLESS_SELF=1`.
The generated `reference/recovery_fixture.inl` contains the final 32 Hz constraint;
do not substitute the earlier experimental 8 Hz helper. Scope changes to this
recovery rig; preserve gameplay and RunLR settings.

## What was verified

Frozen policy on **100 fresh perturbed starts**: **Unreal/Jolt 100/100**, native
MuJoCo 99/100. Balanced front/back, half with added velocity/spin, same initial
states, flat floor and production success gates. No retraining. This establishes
success on that distribution, not identical trajectories or arbitrary terrain.
Those physical tests used a Python policy bridge into actual Unreal/Jolt.
The new ONNX separately passes CPU ONNX Runtime vs PyTorch parity (see report);
its Unreal inference integration still needs a local parity check using the
provided vectors before gameplay deployment.

Training remains stopped. No gameplay assets or active Unreal session were changed
to create this package. Full investigation: `Docs/MimicKitTransfer.md` in Prophecy.
"""

if __name__ == '__main__':
    main()
