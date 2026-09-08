# Root hit response and half-attack targets

All nodes are on **Prophecy Agent** (`Self` in the agent Blueprint).
They do not require adding anything to Blueprint Tick. No hit event is automatically wired.

## Add Root Impulse

Adds to the existing **capsule/mover** velocity, not the pelvis rigid body's velocity.
The call does not change root location, facing, pose, input, or magnetization settings.
Subsequent 30 Hz movement and future-root prediction consume the changed momentum;
the usual capsule sweeps and locomotion braking still apply.

| Pin | Meaning |
|---|---|
| World Linear Impulse | World XY momentum in **kg·cm/s**. Z is ignored: this is the existing ground-plane mover. |
| World Angular Impulse Radians | World Z angular momentum in **kg·cm²/s**. X/Y are ignored: the capsule stays upright. Positive Z turns in positive Unreal yaw. |
| Velocity Change | Default **false**: divide by capsule mass/yaw inertia. **True**: inputs are directly added **cm/s** and **rad/s**, without mass/inertia scaling. |
| Return Value | Success. False for an unregistered/disabled mover, non-finite input, invalid mass, or an angular velocity that cannot fit the mover's shortest-arc representation (180° per policy step). Rejected inputs do not partially apply. |

Example hit event: **Add Root Impulse**, Velocity Change **true**, linear
`(-200, 0, 0)`, angular `(0, 0, 1)` adds **−200 cm/s world X** and **+1 rad/s yaw**.
Existing motion is retained. The steering motor may brake the rotation; a zero
locomotion Turn Scale disables that correction and lets imparted yaw coast.

Supporting readbacks:

- **Get Root Velocity**: actual mover linear velocity (world cm/s), angular velocity (world rad/s), success.
- **Get Root Impulse Mass Properties**: capsule mass in kg and upright yaw inertia in kg·cm², success. These are not the sum of skeletal-body masses.

No jump/vertical-root dynamics or capsule pitch/roll system is added. Root stepping
remains frozen when NN Inference Enabled is false; the impulse node then returns false.

## Get Mass Weighted Pose Error

An on-demand, read-only sum over each unique **currently simulated PHAT body**.
Includes pelvis, legs, upper body, and attack poses. Uses the existing data-only
presented targets, so Show Kinematic Debug Mesh can remain off.

| Output | Definition |
|---|---|
| Linear Error Kg Cm | `Σ mass × (actual world bone position − presented target position)` |
| Angular Error Kg Radians | `Σ mass × shortest world-space axis-angle rotation vector from target to actual` |
| Total Mass Kg | Sum of included body masses. |
| Body Count | Number of included simulated bodies. |
| Return Value | False with zero outputs when no supported simulated bodies/targets are available, including fully Kinematic mode. |

For a 4 kg head displaced 1 cm backward, its linear contribution is a vector
**4 kg·cm backward**. Errors with opposite directions can cancel. These are raw
sums, not averages or unsigned magnitudes. Divide by Total Mass Kg yourself if you
want a mass-normalized result. Angular weighting is by mass, as requested, not inertia.

This measures raw physical deviation; feedback deadbands do not filter it and
magnetization strength is not changed. Sampling **after physics** compares the
completed simulation with that frame's target. Before physics, a newly advanced
target can include the movement physics has not executed yet.

## Global half-attack target radius

- **Set Global Half Attack Target Radius**: positive radius in **cm**, default **125 cm = 1.25 m**. Returns false for zero/negative/non-finite input.
- **Get Global Half Attack Target Radius**: reads that value.
- The value is shared by **all agents in the same game world**, including agents registered later. Changing it on any agent updates active half attacks on their next policy step. Each new PIE/game world starts at 125 cm. Set it on BeginPlay if you want another value.
- **Get NN Attack Target**: requested world target, effective world target, and ghost world target computed from the current policy poses. Returns false when no attack is active. It does not advance inference.

For half attacks, the real lower-policy pelvis is the sphere centre. Targets inside
the sphere stay unchanged; targets outside are projected to its surface, preserving
their 3D direction. The resulting pelvis-relative target is transformed into the
existing ghost pelvis frame—the inverse of the existing upper-body presentation
mapping. This keeps the target coherent when the real agent moves away from the ghost.

Only target preparation changes. The lower ghost NN/history, four-step integration,
upper presentation, and learned Armed/Hit latches retain their existing logic.
Projection does **not** force Hit or remove the learned wind-up. Full attacks are
unclamped and keep their original world target. Existing kick half-mode rejection remains.

## Verification

- `Tools/NN/TestProphecyRootMomentum.cpp`: signed impulses, braking/settling,
  zero-turn coasting, identical predicted/actual eight-step roots, 3,000 normal-path checks.
- `Tools/NN/TestProphecyHitNodes.py`: live Blueprint-callable nodes at 60/5 FPS,
  additive mass-scaled/velocity-change impulses without immediate teleportation,
  independent mass-weighted error calculation, known 1 cm displacement, global
  radius propagation, near/far targets, full bypass, half inference continuation.
- Reports: `Saved/SlashParity/hit_nodes.json` (runtime) and compiler/test stdout.
- `Tools/NN/TestProphecyHalfTargetMotion.py`: moving half `slashL`/`pike` stayed
  inside 125 cm while the roots travelled about 59/127 cm. Both naturally completed;
  learned Hit occurred at policy frames 15/37, not instantly. Report:
  `Saved/SlashParity/half_target_motion.json`.

Impulse mass/inertia conventions were checked against UE 5.7 source and
[Epic's FBodyInstance reference](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/FBodyInstance?lang=en-US).
