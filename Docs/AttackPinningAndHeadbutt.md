# Attack pinning and Headbutt preparation controls

Added 2026-09-13 on **Prophecy Agent** (including BP_ProphecyManualPoseAgent).

## Attack-only length clamps

Two per-agent nodes update the next full-attack pose:

| Node | Enabled + Leeway Cm |
|---|---|
| **Set Attack Foot Clamp** | Caps hip-to-foot reach at the total rest leg length plus leeway. It does not force a bent knee straight. |
| **Set Attack Calf Clamp** | Bounds knee-to-foot length to rest calf length **plus or minus** leeway. |

Both nodes have an **Enabled** pin. False disables that clamp for this agent's
full attacks; set both false to get the unconstrained attack legs. **0 cm** gives
the exact calf length / original maximum leg reach. **1 cm** leaves up to 1 cm
of length variation alone. Outside the allowed band, the pose moves only to the
nearest boundary. Foot/toe rotation is retained and the toe follows any foot shift.
Negative or non-finite leeway is rejected (Return Value false).

Example: **Set Attack Calf Clamp** (`Self`, Enabled=true, Leeway Cm=1). A 40 cm
calf can range from 39 to 41 cm; it is not constantly pulled back to 40 cm.
The interpolation pass uses the same original rest length and leeway, so it
cannot silently remove that freedom or accumulate another centimetre each frame.

These overrides are separate from the manager's locomotion clamps. Half attacks
keep locomotion-owned legs and their usual manager settings. Until a node is
called, existing manager clamp settings still apply to attacks. Calling either
node replaces that attack clamp's old length multiplier with the skeleton's rest
length plus your absolute centimetre allowance. Runtime overrides reset with the
agent instance; wire them in BeginPlay if you want them on every play session.

These are length constraints. They do not add a separate floor-contact solver.

## Per-agent foot pinning

Call **Set Attack Foot Pinning Iterations** with the agent as Target.

- Default: **4**. Accepted values are clamped to **1–60**.
- **60** uses the original training resolution. **4** restores the faster approximation.
- Updates affect the next 30 Hz attack step, including an attack already running.
- Each agent can use a different value in the same inference batch.
- This controls the frozen foot-pinning pass inside full and half attacks. The
  learned Slash pin pass stays at its original 4 steps. It does not change Jolt
  stepping or ordinary locomotion pinning.
- **Get Attack Foot Pinning Iterations** reads the agent property; its default
  can also be set in Class Defaults / Details.

The exported geometry and standalone source audits retain their original 60-step
configuration. Actual gameplay supplies the per-agent setting explicitly. For
training/reference comparisons, set the tested agent to 60, disable Headbutt GT
preparation, and disable both Foot and Calf presentation clamps.

## Headbutt preparation

**Use GT Headbutt Preparation** defaults to **true**. Set it before triggering a
Headbutt; false gives the previous fully neural behavior. It applies to full and
half attacks and to Headbutts started after another attack.

The original animation supplies both hand positions/rotations and upper-arm
orientations until the first learned Armed output. The track uses frames 0–7
at 30 Hz. If Armed is late, it holds the final preparation pose; it does not
force Armed or Hit. The first Armed output returns arm control to the NN.

**Headbutt Preparation Blend Seconds** defaults to **0.1 seconds** (range 0–1).
It is sampled when Headbutt starts and crossfades the current arm pose into GT
with smoothstep. Set it to 0 for direct authored targets. Entry-blend frames are
intentionally a mixture of the starting pose and GT.

The shared file `Content/locomotion/NN/prophecy_headbutt_preparation.json` is about
4 KB with metadata. The native decoder applies the track before its existing
candidate arm calculation, compensating for its baseline/residual representation.
Corrected arm channels also become the next recurrent history. Half mode uses
the ghost pelvis so real pelvis rotation cannot steer this preparation.

There are no extra neural calls, per-agent Timelines, component ticks or second
whole-skeleton evaluations. Normal physical animation and hand attachment still
act on the resulting targets. This is an authored modifier to the learned model,
so Armed timing may differ from fully neural playback.

Source export: `Tools/NN/ExportProphecyHeadbuttPreparation.py`. It verifies source
Armed/fps metadata and quaternion coordinate reconstruction without modifying
training files or weights. Both JSON assets are declared as UFS runtime dependencies.

The user requested to perform gameplay testing themselves. Visual entry/release
quality and incremental runtime cost have not been validated in this pass.
