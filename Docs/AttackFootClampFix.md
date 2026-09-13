# Foot/calf clamp bypass in full-body attacks — 2026-09-12

The current testNN setup chains full-body attacks (kicks, jabs, hooks, overhead attacks, headbutts), switching the agents to Kinematic. Both Clamp Foot and Clamp Calf are true at multiplier 1 during that setup. Re-enabling Clamp Calf at 25 seconds did not change the failure.

The initial 50-second capture reproduced the detached feet numerically. For the player, the generated right calf-to-foot endpoint gap reached 26753.57 cm as repeated attacks continued, although the authored calf length is only 42.563465 cm. The measurement compares the foot position with the reference foot offset transformed by the calf, not camera motion or frame time.

## Cause

`PublishAgentPose` first builds and clamps locomotion. `ApplySlashPose` then replaces the lower body for full attacks. That replacement had an explicit final hand-parent correction, but no foot/calf clamp pass. The settings were valid and active; they simply were not consumed by this pose path. Kinematic attack rendering deliberately avoids the legacy locomotion calf mesh scaling, exposing the detached endpoint.

## Correction

- Apply the existing foot-reach and calf-length controls to decoded full-attack legs alongside the existing hand correction, before caching the visible pose and the established locomotion feedback encoding. Half-attack legs retain their already-clamped locomotion pose.
- Use the mesh's authored upper/lower-leg lengths and the existing runtime multipliers. Align the calf to the resulting endpoint, preserve calf roll through the shortest swing, preserve foot/toe rotations and move the toe with the foot. No mesh scaling, new timestep, smoothing filter, model retraining or changes to raw Slash state/history.
- Preserve the published calf-to-foot local offset after world-space interpolation. Independent position interpolation follows a chord while calf rotation follows an arc; endpoint-only clamps do not preserve that attachment between NN steps. The kinematic evaluator, physical-target array and individual NN foot/toe reads now share the correction. The pose-store flag is conditional on Clamp Calf and is removed on pose cleanup.
- Work is limited to two legs; the clamp helper and interpolation correction allocate no per-frame arrays. No new skeleton update pass.

## Verification

Normal Development Editor build succeeded. All five `Prophecy.NN.PhysicalTargets` tests passed, including new `AttackLegClamps` coverage of disabled controls, authored attachment on both sides, reach, multipliers, coincident endpoints, unchanged foot/toe rotations and scale, interpolation and runtime disabling. Existing forearm tests also passed.

The installed build ran the same current scene for 50 seconds with no Blueprint/map edits. Captured 2881 post-startup samples per foot across two kinematic agents. Endpoint gap max < 2e-12 cm; worst interpolated target gap 0.005563 cm; worst actual PhysicalMesh gap 0.005582 cm (0.05582 mm). These are positional measurements, not a claim to have judged realtime motion visually. PIE was stopped afterward.

Evidence: `Saved/Diagnostics/FootClamp/Before.json`, `Capture.json`, `Comparison.json`, `Build.log`, `Tests.log`. Capture code: `Saved/Diagnostics/FootClamp/Capture.py`. The second capture phase reasserts the already-enabled Clamp Calf setting on the transient PIE manager; it does not edit saved assets.
