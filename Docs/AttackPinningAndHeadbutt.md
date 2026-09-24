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
training/reference comparisons, set the tested agent to 60 and disable both Foot
and Calf presentation clamps. Headbutt GT preparation has been removed.

## Headbutt preparation removed2026-09-24

The former modifier replaced both hands and upper-arm orientation with an authored
GT track before learned Armed, writing the result back into recurrent history.
It has been removed at the user's request. Full/half headbutts and live family
updates now use the checkpoint's arms throughout, with ordinary shared arm/roll,
clamp and presentation controls unchanged.

Removed entry capture, track loading, per-step settings, native pose override,
warmup fingerprint input and dedicated staging dependency. The two old properties
remain deprecated and inert solely for saved Blueprint compatibility, hidden from
editable agent defaults. Retained private storage is unused so this Live Coding
change does not resize already allocated actors, managers or native models.
The old JSON and exporter remain historical artifacts and are not loaded.

Installed in the normal editor build2026-09-24 during the authorized checkpoint
selector restart. Fresh pose Blueprint compiles status3. Short owned PIE test
successfully advances full and half headbutts with checkpoint184064 and shares
the three-agent batch. No runtime references to preparation settings/track remain;
this was a lifecycle check, not a visual headbutt evaluation.
