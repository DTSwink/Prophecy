# Regional attack recovery

## Optional Walk foot-rotation source

**Set Attack Recovery Foot Rotation From Walk** (Agent, Enabled=true) opts an
agent into Walk foot orientation during attack recovery. It is off until called.
Call it in delayed BeginPlay or Special/Attack Ended; toggling it during a return
does not restart the translation blend. Disabled immediately restores the usual
rotation selection.

Both feet use their own existing leg hold/blend duration, including the mapped
kicking/non-kicking durations after kickL/kickR. Normal/zero-duration leg regions
remain bypassed. While translation follows its configured source→normal blend,
rotation follows Walk→normal on that same timeline. Thus for the user's current
Run→Walk recovery, foot rotation comes entirely from Walk throughout. If normal
locomotion is Run, rotation fades back to Run rather than snapping at retirement.

Only the two foot rotation fields change source. Pelvis, ankle prediction,
thigh rotation, toe articulation and pin selection retain their existing source
weights. Selection happens before rotation tempering, foot rolling, floor checks
and leg reconstruction, so these existing systems see the actual chosen foot
orientation. Their resulting contact corrections can naturally change ankle
positions; this does not freeze the final world-space position numerically.
The accepted result feeds both recurrence and upper-body conditioning.

The override applies after full/half attacks, including kicks, and is absent
during specials or after defense-only exits. New specials/reset cancel the
current return; the configured checkbox remains available for future attacks.
The ordinary recovery clock retires each foot independently. No additional
timer, inference or rotation processing remains after completion. While active,
a Run-only translation may require the existing batched Walk evaluation too.
It shares that evaluation with all existing Walk consumers.

Validation2026-09-23: Live Coding build succeeded (375.34s), reflected node enable/
disable calls succeeded, pose Blueprint compiled with status3 and zero stale agent
types. Four focused native tests passed: recovery rotation timing/role mapping,
rotation-only fields, existing regional recovery, and the60-tick clock. No scene
test or Blueprint wiring/save was performed; the node is ready for user testing.

`Set Attack To Locomotion Blend` configures the next attack exit. Pelvis, Left Leg
and Right Leg each have **Source** (Normal, Walk, Run), **Hold Duration Seconds**,
then **Blend Duration Seconds**, in that order. Defaults are Run, 0 and 1 for each
region. The old internal pin names are retained so reordering preserves connections
and values.

`Set Kick To Locomotion Blend` has Source/Hold/Blend controls for **Pelvis**, **Kicking Leg**
and **Non Kicking Leg**. Roles automatically map to left/right for kickL/kickR.
After kickL/kickR, the agent automatically selects that profile. Other attacks use
`Set Attack To Locomotion Blend`. Until the kick setter is called, kicks retain the
regular profile. A regular setter in On Attack Ended cannot overwrite an explicitly
configured kick handoff; the matching setter can still configure that handoff before
its first prediction. No new per-frame selection or additional clock is introduced.

The redundant **Force Run** pin has been removed. Each region's **Source** is now
the sole choice; set that region to Run when needed. Existing Source connections,
holds and blend durations are retained when nodes are refreshed.

For either kick, choose Kicking Leg Source=Walk and Pelvis/Non Kicking Leg Source=Run. This selects
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

September22 kick-profile/Hit validation: normal editor build succeeded (108.36s),
testNN reopened, both new nodes reflected, and all three existing recovery nodes
refreshed with other values/connections preserved. Pose Blueprint compiled and saved.
Six focused tests passed at19:14:49UTC: KickProfiles, AttackRecovery, ReturnTimeline,
SeparateReturns, SixtyTickClock, and Jolt Sword AttackCollisionPhases. The latter
checks native owner-pair restoration at Hit for simulated and attached swords,
retained attack context, repeated refresh, and stable body/joint counts. No scene
rollout. Evidence: `Saved/Diagnostics/KickProfilesValidation.txt`.


September22 kicking/non-kicking refinement: Normal editor build passed115.26s; final test-only rebuild passed60.75s. Unreal reopened on testNN, both role nodes refreshed with existing values/links preserved, new non-kicking inputs copied from shared feet, and pose Blueprint compiled status3 and saved. All11 focused tests passed20:21:05UTC (role mirroring, per-axis pose/toes, return/hold retirement, reset, regional policy, calf continuity and60-tick clock). Initial role-test rotation assertion differed by one float ULP; corrected its tolerance to1e-6, with no gameplay change. No gameplay rollout. Evidence `Saved/Diagnostics/KickRolesValidation.txt` and `KickRolePinValidation.json`; asset backup `KickRoles-BeforeRefresh.uasset`.
