# Head hitch at attack entry — October 3

Fixed and loaded October 3, 00:24:16 Warsaw (October 2, 22:24:16 UTC). User Blueprint/settings unchanged. Detection history follows; see the fix below.

Current scene: first full Pike triggers tick169, first policy prediction tick170. Attack-start FK core inertia enabled Hold .1, Blend .3, Response .25, Momentum/Alpha1. Pelvis entry inertia enabled translation19 ticks and rotation10 ticks, strengths1. Hand entry inertia also enabled.

Two owned, bounded240-tick captures completed and ended only their own Play worlds. Baseline and core_off physical poses match exactly through169. The latter cancels only core inertia after recording169, before the first attack publication; no saved tuning changes.

In the fixed attack-entry frame, head lateral displacement relative to pelvis:

| Pose | Tick169 (cm) | Tick170 | Tick171 |
| --- | ---: | ---: | ---: |
| Presented baseline | 0.088378 | -1.114977 | -0.179312 |
| Physical baseline | -0.071824 | -1.100376 | -0.131824 |
| Presented core disabled after169 | 0.088378 | -1.114977 | -2.920244 |
| Physical core disabled after169 | -0.071824 | -1.100376 | -2.888423 |

The physical head shifts1.02855cm laterally at170 and returns0.96855cm at171. Presented target shifts1.20335cm and returns0.93567cm, so physics follows an existing target reversal.

Every presented core rotation (spine01..05, neck01/02, head) relative to pelvis is identical at169 and170 to about3e-14 degrees. Head position relative to pelvis is also identical. Meanwhile presentation-stage pelvis inertia advances rotation. At171 core motion resumes and reverses the lateral displacement. Core-off preserves the same first170 step but removes the following reversal. This isolates an interaction between entry presentation timing and the core-inertia path, rather than a physical constraint or extra raw NN jitter. It does not establish that removing inertia is the desired fix.

Relevant code: physical-start presentation history in AdvanceSlashAttacks copies the latest displayed pose into Slash.VisibleWorldPose before first prediction; first attack publication has interpolation alpha0. The pelvis inertia ApplyPelvis stage advances separately at render/game-tick cadence. Core spring endpoints are computed at the fixed policy interval and become visible from alpha.5 on171. Investigate boundary phase alignment without changing the accepted NN input/output or undoing the previous physical-entry pelvis fix.

Evidence: Saved/Diagnostics/HeadAttackEntry20261003/{baseline,core_off}.json, matching *-nn.jsonl and *-graph.txt, analysis.json. Capture script Saved/Diagnostics/CaptureHeadAttackEntry.py. No runtime fix attempted or compile needed.

## Fix and verification

At the first physically seeded full-attack publication, keep the pelvis/leg history correction but restore the active FK core to its outgoing local spring endpoint. Carry descendant transforms with those rotations, preserving their local rotations/translations. Alpha weights this entry correction. This only prepares the interpolation history; it does not integrate the spring, advance its clock, change NN recurrence, or run on inactive core inertia. Half/kinematic starts already retain their ordinary endpoint history.

Implementation: ProphecyAttackStartFKCore::PrepareEntryPose, called once by the physical-entry history preparation in AdvanceSlashAttacks. Existing state layout and settings remain intact.

Matched 240-tick replay completed; owned Play ended. Before169 all physical poses match exactly. First six captured NN inputs/outputs match exactly, and presented pelvis169–174 matches exactly. The isolated one-frame lateral reversal is gone:

| Pose | Tick169 (cm) | Tick170 | Tick171 |
| --- | ---: | ---: | ---: |
| Presented fixed | 0.088378 | 0.631885 | 0.652358 |
| Physical fixed | -0.071824 | 0.655536 | 0.762323 |

These are lateral head positions relative to pelvis in the fixed entry frame. Normal subsequent attack motion is retained; this is not a claim that the head never changes direction later. At172 the presented head matches the original rollout again.

FKCoreBoundary, FKCoreClock and FKCoreSpace all passed October3 at00:25:35 Warsaw. Boundary covers alpha0/.5/1, carried local transforms, preserved pelvis and no extra spring/clock advancement. Runtime build106.52s; Live Coding loaded successfully. No reflected changes, asset saves or Blueprint edits. Normal DLL rebuild remains required before a cold launch.

Evidence: fixed.json, fixed-nn.jsonl, fixed-graph.txt, fix-verification.json; repeatable analysis verify_fix.py under Saved/Diagnostics/HeadAttackEntry20261003.

## Residual twitch confirmed after user retest

The first fix is incomplete. A fresh unchanged-settings240-tick owned replay exactly matches the earlier fixed target poses165–175. The reversal-only assertion passed but missed a one-frame lateral speed spike. Physical head motion relative to pelvis in fixed entry axes is0.154720cm from168→169,0.727360cm from169→170, then0.106788cm from170→171. Presented target already moves0.078857,0.543507,0.020473cm over those intervals. Thus a smaller visible kick remains at170; it is primarily in the commanded pose, with physics increasing its size. Do not claim the hitch fully resolved. No further runtime changes made during this confirmation. Evidence: residual.json, residual-nn.jsonl, residual-graph.txt and residual-analysis.json. Owned session ended normally.

## Residual diagnosis: incompatible outgoing velocity sources

No runtime change during diagnosis. Fresh owned velocity_diagnosis replay records physical angular velocities and completes normally.

At the first attack, pelvis inertia has no rolling idle history (deliberate disabled/inactive-cost rule). ProphecyAttackStartInertia::Begin falls back to the two supplied seed poses. TriggerAgentNNAttack supplies PhysicalSeed.Previous/Current when SetSpecialStartFromPhysical is enabled. ProphecySpecialStart::Sample constructs Previous by integrating the measured physical angular velocity backwards for one NN interval. Consequently pelvis E.AngularDelta is physical angular velocity /60. In contrast, FK core Begin samples previous/future animation-target local rotations. These are different motion sources. The pelvis begins its presentation correction from the displayed target orientation but advances it using physical angular velocity.

Measured proof: the presented pelvis world rotation increment169→170 equals the physical pelvis angular velocity captured at169 divided by60, error1.5409e-9 radians. Its XYZ rotation-vector components are[1.521947,0.723676,0.159538]degrees; the preceding displayed step was[1.023422,1.114732,0.906817]degrees.

Exact symmetric decomposition of presented head lateral steps (cm) into pelvis rotation and head movement in pelvis local space:

| Ending tick | Pelvis contribution | Core contribution | Total |
| --- | ---: | ---: | ---: |
|169|-1.677664|1.756522|0.078857|
|170|-1.206171|1.749678|0.543507|
|171|-1.216032|1.236504|0.020473|

Core contribution is essentially continuous169→170. The unexpected change is in the pelvis contribution; its source switch creates the target speed spike. Core spring response subsequently reduces core movement at171. Physics amplifies the target's0.544cm lateral step to0.727cm.

Offline causal check, preserving the exact recorded170 head-in-pelvis pose and pelvis position: replace only170 pelvis angular increment with the preceding displayed angular increment. Head lateral step becomes0.073674cm rather than0.543507cm, matching the preceding0.078857cm step. This is an isolated mathematical counterfactual, not a loaded runtime fix or claim about a complete subsequent rollout.

Recommended correction: use compatible outgoing motion for the presentation-layer pelvis/core inertia handoff. Preserve physical attack NN initialization and tick timing. Do not simply disable pelvis inertia or hide this with extra head damping. The original pause diagnosis explained the earlier reversal; the remaining speed spike is specifically a physical-versus-target velocity mismatch.

Evidence: velocity_diagnosis.json, velocity_diagnosis-nn.jsonl, velocity_diagnosis-graph.txt, velocity-diagnosis-analysis.json under Saved/Diagnostics/HeadAttackEntry20261003.

## User-requested inverse counterfactual

Tested the inverse of the prior single-frame calculation: keep the recorded pelvis170 pose/motion unchanged; change only the FK core's outgoing angular velocity to the physical seed velocity. Start from the displayed169 pose, preserve parent-local attachment translations, and advance each spine/neck/head joint by one1/60 game tick. Momentum/Alpha are1 in the captured user setup. The initial NN trace contains physical previous/current core local rotations at offsets82/172; decode uses the production6D rotation convention and mirrored Y basis. Reconstructed physical spine05/head orientations match the captured bodies within0.0000044degrees, validating the source/convention.

The target head lateral step169→170 falls from0.543507cm to0.099807cm. The preceding168→169 step was0.078857cm. Thus physical core velocity also suppresses the isolated frame170 spike, without changing pelvis inertia. This does not test the complete spring/blend rollout or resulting physical simulation and is not a claim of a loaded runtime fix. No code, Blueprint, tuning or editor session changes in this inverse test.

Reproduction: Saved/Diagnostics/HeadAttackEntry20261003/test_inverse.py; result inverse-velocity-analysis.json. If implementing the user-preferred physical-core variant, preserve the displayed starting pose/phase and use physical outgoing angular velocity consistently; simply swapping in a different physical pose introduces a separate jump and would not match this test.

## Mode synchronization loaded

User requested physical starts in simulation and NN starts in Kinematic for both pelvis/core. Implemented and loaded01:01:45 Warsaw; source parity verified in three owned replays, five tests passed. See [current source contract and residual limitation](AttackStartFKCoreInertia.md#mode-synchronized-pelviscore-sources--october-3). Small physical head entry twitch remains; do not claim fully cured.
