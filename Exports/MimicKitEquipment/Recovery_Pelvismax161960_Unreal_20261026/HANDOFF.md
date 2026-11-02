# Recovery checkpoint → Unreal

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
