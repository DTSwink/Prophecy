# Regional attack recovery

`Set Attack To Locomotion Blend` configures the next attack exit. Pelvis, Left Leg
and Right Leg each have **Source** (Normal, Walk, Run), **Hold Duration Seconds**,
then **Blend Duration Seconds**, in that order. Defaults are Run, 0 and 1 for each
region. The old internal pin names are retained so reordering preserves connections
and values.

For kickR, choose Right Leg Source=Walk and Pelvis/Left Leg Source=Run. This selects
complete policy regions: pelvis position/rotation; each leg's ankle, foot rotation,
thigh rotation, toe articulation and corresponding pin outputs. The two checkpoints
receive the same existing recurrent/root input. This does not select a separate
network per bone or reset the NN history.

Each region holds its source, then smoothstep blends to the current **normal**
walk/run selection, including its ordinary blend. It no longer unconditionally
finishes on walk. Movement intent, automatic run threshold and normal directional
blend settings remain authoritative. Root trajectory is unchanged.

Each authored second is 60 unpaused world ticks, independent of FPS/time dilation.
Different holds and durations retire independently. Duration=0 or Source=Normal
bypasses a region entirely (including hold). If all regions bypass, no recovery
clock, extra policy inference or recovery pose correction is scheduled. Disabling
a region applies immediately; positive edits apply at the next handoff. Calls in
On Attack Ended can configure the current handoff before its first prediction. Starting
a new attack or resetting cancels the previous recovery.

Checkpoint inference is selected from all three weights: an exact run-only or
walk-only pose uses one policy, mixed regions require both existing batched policy
passes. Pure endpoints are copied exactly. Each leg uses its own foot/pole geometry
in presentation and pelvis inertia, with previous/current weights retained for
interpolation. Corrected mixed poses feed recurrence and upper-body conditioning.
Walk/run-dependent magnetisation, tolerance and damping profiles use each physical
leg's weight too; pelvis and upper-body profiles retain the pelvis weight. Uniform
profiles and inactive-context fast paths remain unchanged.

When pelvis and a leg use different weights, the existing leg solver transports
that leg from its source pelvis to the mixed pelvis after pinning. It honors the
leg-reconstruction diagnostic switch and current outer-reach clamp setting. When
tempering already resolves the chain, it performs that work only once using the
accepted tempering solver. This does not change that solver's knee guidance.

The legacy scalar walk/run-weight getter describes the pelvis mixture. The NN
diagnostic capture also records `left_walk_weight` and `right_walk_weight`.

Existing pose-agent Blueprint nodes are explicitly upgraded by
`Prophecy.Editor.UpgradeFineGrainedBlends`: old translation values/wires are copied
to both XY and Z; old recovery timings are copied to all three regions. The command
only touches nodes present in the pre-update audit, backs up the live asset, compiles,
and leaves it unsaved. It does not choose per-attack settings for the user's graph.

Validated2026-09-20 with a normal Editor build (17 actions,112.83s; a later test-only
float-tolerance adjustment rebuilt in20.59s). Nine focused tests passed across the
headless report and final reopened-editor checks: recovery source/timing, regional
pose fields, 60-tick clock, tempering axes/returns, reset baseline, physical-context
selection and damping. Pose-agent compile status3, no stale native types. The
upgrade changed five nodes, adding25 pins and16 inherited values/connections;
all pre-existing graph links remained, apart from native CDO/output-default
normalization after restart. The verified pose-agent was saved. User scene testing
remains separate; no combat rollout or visual-quality claim.
