# Kick foot joint leeway

**Locomotion calf-clamp inheritance, September25:** physical feet now use an explicitly enabled locomotion calf clamp's current±leeway for joint travel and drive-target allowance. Snapshot blends/restores are read directly. Specials retain their own rules; kick allowance remains configured by `Set Kick Foot Joint Leeway` (default0), extension-only while attacking. On locomotion return, the physical range is−locomotion leeway through max(locomotion leeway, current kick return). This does not increase the user's attack5cm setting. [Implementation and validation](PhysicalFootHover20260925.md).

**Physical target continuity, September25:** after a full special, the physical foot clamp endpoint now follows the same signed calf-length return as presentation. It no longer jumps to rest length while the kinematic calf is still returning. Configured physical target leeway is applied around this endpoint; physical joint limits and active kick allowance remain unchanged. [Measured simulation evidence](SimFootExitRecovery.md).

## Current behavior, September24

**Shared special return:** full non-kick attacks, parry and dodge now use the same
outgoing signed calf-length/render continuity without loosening physical ankle
joints. It reuses the configured kick return duration when present, otherwise60
ticks; explicit configured zero duration stays immediate. Half attacks retain
locomotion legs. Active-kick joint/pose recovery is unchanged. See
[the paired jabR regression](CalfSnap1495.md) for evidence and scope.

The extension-only **attack-time NN pose override is removed**. The checkpoint owns its foot-distance/floor correction. While physical allowance is active, foot magnetisation uses the published foot target directly. Mode-specific foot/calf clamps remain bypassed during that allowance, as before.

**Recovery length continuity:** after a full kick returns to locomotion, capture each calf's actual outgoing target length independently. Its signed difference from the reference length fades to zero using the existing `Set Kick Foot Joint Leeway` return duration (60 ticks per authored second, no hold). This supports both extension and compression from the new checkpoint. Reconstruction and pelvis inertia use that current effective length. After pose interpolation, knee/segment-aim correction preserves the ankle position and rotation; it does not push the foot down onto the old calf axis. Unreachable endpoints keep their existing positions and use the nearest feasible knee triangle. No attack pose or new inference is involved.

The correction is active only during that finite configured return. Zero leeway disables the kick joint allowance; pose-only special recovery can still run. Zero configured duration bypasses; new specials, reset, completion and world teardown remove the correction. The leg-chain diagnostic toggle also bypasses it. Existing physical constraints remain extension-only; signed NN length recovery does not add physical joint compression freedom.

Kinematic rendering also retains the attack's authored calf scale during recovery. Applying locomotion's ordinary mesh stretch immediately at exit would snap the visible calf tip to the ankle despite smooth joint-centre distances. The gap now closes with the length return; ordinary locomotion stretching resumes at rest length. Existing authored transverse scale is preserved.

Validation: six focused checks passed;15-exit kinematic replay reduced the5cm two-tick collapse to below0.017cm. Final getter replay verifies that the displayed physical mesh and Blueprint target reads agree within0.00065cm. Both signs of length recovery follow the60-tick curve. [Detailed evidence and scope](KickExitCalfLengthRegression.md).

The node still controls Jolt ankle-joint allowance and its return duration. It does not change the checkpoint's±5cm range. Existing physical constraints are a separate setting: this change does not grant additional physical compression or transverse joint freedom. Defaults and60-tick duration convention are unchanged; no pose-recovery state or correction remains after completion. See [new checkpoint contract](AttackCheckpoint123793.md).

## Historical implementation through September21 — superseded pose inheritance

**Set Kick Foot Joint Leeway** configures an agent's Jolt ankle joints:

- **Leeway Cm = 0** by default: disabled, existing behavior.
- **Return Duration Seconds = 1** by default: 60 unpaused game ticks, regardless of FPS or time dilation. Zero restores immediately.

Call before a kick, for example during BeginPlay. On kickL/kickR start, both foot-to-calf joints immediately allow extension from 0 to the configured distance along their respective calf's length. This direction comes from the reference foot offset in calf space, not world up or an assumed bone Z axis. No additional sideways movement or compression is granted. Rotations, authored angular limits, angular-limit blends and damping remain unchanged.

The physical foot drive target also admits that axial extension toward the NN foot position, otherwise the default target clamp would negate the joint allowance. Existing general physical foot-target leeway still behaves as configured.

The NN presentation now inherits the same allowance, including kinematic playback. While positive, it temporarily replaces the mode-specific foot/calf presentation clamps with the same reference calf-axis range. This prevents locomotion's hard calf clamp from removing the allowance at attack exit. The decoded published poses and the post-interpolation foot/toe correction agree; that final correction receives each 60 Hz return value even between 30 Hz NN publications. It uses the original skeleton offset, not a stretched pose as the next rest length. It changes foot/toe positions, not their rotations or the raw checkpoint recurrence. At zero the override is removed and ordinary authored clamp settings resume. No additional timer or NN inference is introduced.

Every attack stop (completion, cancellation, replacement or interruption) starts a smoothstep return from the current allowance to zero, with no hold. Another kick immediately restores its configured allowance and cancels the return. Other attacks do not start an allowance. Setting leeway to zero explicitly cancels/restores immediately. Positive configuration changes during a kick apply immediately; during an existing return they configure future kicks.

At exit, each foot's **actual presented axial extension** is captured separately. It fades on the same 60-tick-per-second clock, inside the shrinking joint allowance. Locomotion tempering/regional recovery and pelvis-inertia reconstruction use that foot's effective calf length; the existing knee-pole guidance is unchanged. The final presentation correction uses the same returning length, including ticks between NN publications. This preserves extension even if a newly decoded locomotion pose is already shorter. It does not stretch both feet to the configured maximum. Another kick clears the captured return; reset, completion and pose/world teardown remove its sidecars. No additional ticking exists outside the existing finite return.

Reset cancels the return and closes the joints while retaining the configuration for future kicks. Rig recreation reapplies a still-active allowance. EndPlay/world teardown removes transient state. No fade callback exists during a held kick allowance or after completion; the extra translation constraints exist only while the allowance is positive.

Implementation preserves the existing anatomical SixDOF angular frame and angular warm start. While enabled, a temporary translation-only SixDOF supplies the calf-aligned extension range and two locked transverse axes. At zero it is removed and the original joint's exact translation bounds restored. No mesh asset, PHAT asset, checkpoint or Blueprint wiring is changed.

Focused checks passed2026-09-21: `Prophecy.Jolt.Joints.FootExtension` (rotated parent/unaligned PHAT axes, extension bound, sideways lock, unchanged angular limits, restoration), `Prophecy.Joints.KickFootLeeway` (target projection and kick/return/reset timing), and `Prophecy.Jolt.RigWorld.FootExtension` (native bridge and constraint lifetime across update/recreation/teardown). Loaded through Live Coding; pose-agent Blueprint compiled successfully. Gameplay scene testing is left to the user.

NN inheritance follow-up passed `Prophecy.NN.PhysicalTargets.KickLeewayInheritance`, the existing `AttackLegClamps` regression and `Prophecy.Joints.KickFootLeeway` on2026-09-21 14:02UTC. This includes switching from unclamped attack to hard-clamped locomotion, a changing allowance without another NN sample, preserving a custom baseline length at retirement, and cleanup. Blueprint compilation also passed.

## Scene diagnosis and correction, 2026-09-21

The initial presentation-only change did **not** guarantee a smooth physical-foot return when locomotion leg reconstruction resumed. Numerical capture of the user's setup confirmed the reported snap across 15 kickL exits. The Blueprint configures 5 cm / 1 second. At the second exit, the right calf-to-foot physical distance was 47.490 cm, then 44.492 cm, then 42.237 cm on successive 60 Hz samples. Its next NN target changed from 47.563 cm to the reference 42.563 cm at the exit, with the displayed target completing that change in two game frames.

Cause: the locomotion reconstruction in `ProphecyNNLocomotionManager.cpp` still constructs `FPelvisLegGeometry` with `Impl->LocalOffsets[Limb.End].Size()`, then `ResolveTemperedLeg` / `ResolvePelvisLeg` solves a fixed-length calf. It does not consume kick extension. The downstream `ApplyKickExtension` only caps the extension present in that already reconstructed pose; it cannot restore extension that the upstream solve removed. The joint allowance can therefore fade correctly while magnetisation immediately follows a shortened target.

A separate transient Play comparison disabled only leg-chain reconstruction. Across four exits, the next right-foot target stayed at 47.563 cm at exit and then followed 47.547 / 47.500 / 47.423 cm as the allowance returned. This isolates the immediate target collapse to reconstruction. That comparison also produced much worse left-leg transients; disabling reconstruction is **not** a solution. Both diagnostic Play sessions were stopped after capture; no Blueprint/map settings or code behavior were changed or saved.

Implemented the per-foot captured return and consistent effective reconstruction length described above. Gameplay patch loaded via Live Coding at14:37:16UTC. The identical 24-second setup completed 15 exits with reconstruction enabled. Maximum right-foot contraction over the first two exit ticks fell from5.2885cm to0.1831cm; left fell from2.8827cm to0.2650cm. All captured active returns followed their expected smoothstep lengths within0.002cm. Across each first-second recovery window, maximum calf target rotation steps did not increase overall (left30.70→30.07degrees; right19.10→13.06degrees). These are bounded scene measurements, not a guarantee for every checkpoint/setup. Ordinary authored clamp behavior resumes when the return ends. Diagnostic PIE ended; no user asset saves or graph edits.

Evidence: `Saved/Diagnostics/KickFootSnap.json` (24 seconds, 15 exits), `KickFootSnap-no_reconstruction.json` (7 seconds, four exits), captured by `KickFootSnapCapture.py`, summarized by `AnalyzeKickFootSnap.py`.
Corrected evidence: `KickFootSnap-fixed.json`, `KickFootSnap-comparison.json`, and `CompareKickFootSnap.py`, including independent left/right lengths and return-curve assertions.

Final patch loaded14:40:20UTC; all three focused tests passed14:40:53UTC: `KickFootLeeway`, `AttackLegClamps`, `KickLeewayInheritance`. Regressions cover a shortened reconstruction input, shared publication/interpolation return length, independent captured extensions, the tick clock, new-kick cancellation and retirement. The final recompilation changed only a float-comparison tolerance in the clock assertion (1e-5); gameplay behavior matches the captured patch.

The2026-09-23 normal Editor build incorporated the later signed-length and render-scale fixes. Direct evaluated-mesh verification across five complete recovery windows now checks calf-tip/ankle continuity as well as joint-centre distance: calf scale remains unchanged, the largest first-tick left gap change is0.004045cm instead of4.907983cm, and each gap converges below0.02cm. See [current evidence](KickExitCalfLengthRegression.md). The authorized pose Blueprint save/restart is complete; diagnostic Play ended.
