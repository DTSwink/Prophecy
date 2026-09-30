# Half-attack spine compensation

Blueprint node: **Enable Spine01 Compensation Half Attack**, category `Prophecy | Agent | Attack`.

Inputs:

- **Agent**: defaults to Self.
- **Enabled**: set the per-agent toggle. The feature starts disabled; executing the node with this checked enables it.
- **Distribute Along Spine01 To Spine05**: defaults unchecked. Unchecked puts the complete correction at `spine_01`; checked applies one fifth at each of `spine_01`, `spine_02`, `spine_03`, `spine_04`, `spine_05`.
- **Compensate Position**: defaults unchecked. Also counter-steers the upper body toward the current real attack target when its spine attachment moves away from the ghost's. Works with either distribution setting; requires Enabled.

Return value indicates whether the setting was accepted. Call once during setup or when changing the setting; no Tick wiring is needed. A change during an attack takes effect on its next pose update.

The reference is the **real NN pelvis**, before the upper-body graft, versus the current independent ghost pelvis. Their rotations are compared in the same coordinate frame, including the ghost's fixed world anchor and the real agent's moving carrier. The counter-rotation applies only to half-attack presentation; it does not rotate the locomotion pelvis/legs, change the real target, or feed the compensated torso back into the ghost.

Single-joint mode preserves the normal spine attachment position and counter-rotates its upper subtree around that point. With position compensation off, its world orientation then matches the ghost. Distributed mode uses equal quaternion increments along the five-joint chain, preserving local attachment translations and lengths. The accumulated correction reaches 100% at `spine_05`; attached arms/head follow their corrected spine ancestor. Distribution can change the chest's position as the chain bends. Fixed anatomical hand attachment, roll and arm inertia still apply afterward.

Position compensation transports the ghost's target through the torso mount, then rotates that virtual target ray toward the current real target about `spine_01`. A leftward displacement therefore counter-steers right. It preserves the swing's relationship to its target instead of pointing the hand directly at the target throughout wind-up. Single-spine mode uses one shortest-arc quaternion. Distributed mode performs at most two additional five-joint evaluations to account for chest movement, accepting only corrections that reduce virtual target error. Both use current target data, including retargets; neither changes ghost inference or recurrent state. Rotation cannot remove radial reach error without stretching or translating the skeleton, so this does not guarantee a physical weapon hit.

Disabled uses the original mounting branch: no compensation math, transform construction/copies, spine-chain lookups, sampling, timers, delegates, inference or per-frame state allocation. Only a cheap enable guard is added at an existing half-attack pose update; an empty enabled set bypasses even the per-agent lookup. Full attacks and locomotion never enter either compensation mode. Position unchecked skips all position math; its empty sparse set avoids the per-agent lookup. Disabling removes all active setting entries. Initial-agent reset captures/restores all three settings; EndPlay removes them. No retained agent/manager layout changed.

Implementation: `ProphecyGhostAttackLibrary` exposes the node, `ProphecyHalfAttackCompensation` owns sparse toggle/reset state, and `ProphecyHalfAttackMount.h` supplies the quaternion/chain math used by `ApplySlashPose`.

## Verification

Focused native tests cover unrelated carrier and pelvis yaw/pitch/roll, wraparound near +/-180 degrees, spine attachment, upper articulation, equal fifths through the distributed chain, local attachment/length preservation, unchanged lower body, defaults, disable and reset/removal.

Live paired captures compare a full attack followed by a half attack with a turning pelvis and a mid-attack retarget. Native checkpoint traces independently reconstruct ghost world rotations and verify that ghost inputs/outputs are unchanged. Evidence is under `Saved/Diagnostics/SpineCompensation/`; reproduction scripts are `Tools/NN/SpineCompensation/`.

Rotation-only validation on September 27 local (before the position option):

- Live Coding patch **35** compiled and loaded **2026-09-26 23:43:26 UTC**. The reflected node, including both Boolean inputs, was successfully invoked in the live editor. No editor restart or asset save was performed; incorporate these reflected changes in the next normal build before a fresh launch.
- **2/2 focused native tests passed:** `Prophecy.NN.HalfAttack.PelvisMount` and `Prophecy.NN.HalfAttack.SpineCompensation` (including distribution and setting lifecycle).
- Three matched live captures (disabled, single-joint, distributed): **98 attack samples per run**, including 58 full and 40 half, with **47 ghost inference steps**. Full attacks, lower-body poses, targets, and raw ghost inputs/outputs were exactly unchanged across all three runs.
- Single-joint mode: maximum spine world-orientation discrepancy from the raw ghost **166.10253 degrees disabled → 0.0000241 degrees enabled**.
- Distributed mode: each spine matched its expected cumulative 20/40/60/80/100% correction within **0.0000436 degrees**. Maximum local joint-attachment discrepancy was **1.39e-13 cm**. Spine01's attachment to the pelvis remained unchanged.
- All owned PIE sessions ended and trace capture was disabled afterward. The feature remains off by default until the user executes the node.

## Position compensation validation

- Runtime Live Coding patch **36** loaded September 27 **00:02:09 UTC**. **3/3** focused tests passed: PelvisMount, SpineCompensation and PositionCompensation. Coverage includes lateral counter-steering, zero-length and opposite rays, unrelated coordinate frames, unchanged pelvis/legs, preserved attachments and all setting/reset combinations. No full suite was run.
- The existing Blueprint call needed reconstruction for its new checkbox. `Prophecy.Editor.RefreshSpinePosition` refreshed exactly **one** node; prior values/links were preserved and Blueprint status is **3 (up to date)**. The added pin defaults false. The asset was left unsaved; no unrelated graph edits or editor restart. Editor helper patch4 loaded 00:08:42 UTC.
- Four live captures use the user's current pike setup, including full-to-half switching around tick127. Each records126 samples, including18 half-attack samples. Single-spine maximum target-ray angular error **11.44058 degrees → 0.0000157 degrees**. Distributed maximum **11.80394 degrees → 0.50037 degrees**.
- Transported-target mean positional error: single **15.3212 → 8.8242 cm**, distributed **15.4691 → 11.2316 cm**. At tick141, remaining errors are20.325 cm and25.188 cm respectively, largely radial reach that rotation cannot remove. These measurements describe the mounted ghost's target proxy, not a confirmed physical weapon collision.
- Before the half transition, captures are exactly equal. Real targets and raw ghost inputs/outputs/anchors remain exactly equal for each pair. In the live physical scene, later lower-body positions differ by at most **0.00630 cm** single / **0.000962 cm** distributed; they are not bit-identical after the changed upper-body pose. The isolated geometry tests verify that the mounting function itself leaves lower transforms unchanged.
- No additional checkpoint calls, per-frame allocations, history, timers or delegates. Position unchecked bypasses position math. Both PIE and native tracing were stopped after capture. Evidence: `Saved/Diagnostics/PositionCompensation/`; scripts: `Tools/NN/SpineCompensation/CapturePositionCompensation.py`, `AnalyzePositionCompensation.py`, `ComparePositionRuns.py`. Pass capture arguments `single_off 0 0`, `single_on 1 0`, `distributed_off 0 1`, `distributed_on 1 1`, sequentially after each prior owned PIE session finishes.
