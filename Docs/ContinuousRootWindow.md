# Continuous locomotion root window

`Get Continuous Locomotion Root Window` (Agent, default Self) returns world-space transforms and time offsets evaluated when the node executes:

- Index **0**: the currently applied/displayed root low point and yaw; time **0**.
- Indices **1–8**: predicted future roots, spaced by the policy interval (1/30 second at 30 Hz).
- Return Value is false before an input window exists, when inference is disabled, or during a full attack or full-body NN Dodge. Half attacks and upper-only Parry retain the locomotion window.

This is a separate getter. `Get Locomotion Root Window` still returns the exact last encoded NN input with **10** entries: previous at index 0, current at index 1, eight future roots. Neither getter modifies NN inputs, the mover, smoothing, physics, or animation.

The displayed root interpolates from the previous published root to the current one. The continuous getter samples the encoded trajectory at that same fractional phase: previous-to-current for now, current-to-future1 for the first future sample, and so on. Position interpolation is linear; orientation uses quaternion slerp. The last sample remains inside the known prediction horizon, so no extrapolated endpoint is needed. A single rigid correction aligns the sampled window with the applied root, including capsule collision/floor correction.

There is no extra delay beyond the existing presentation interpolation. Future samples are predictions and can change when a new policy window incorporates input or collisions; the getter cannot guarantee an unchanged future after those events. It does remove the raw getter's fixed 30 Hz current-root hold between policy updates.

Cost is on demand only: existing manager lookup and window decode, eight future interpolations plus one shared-origin interpolation/correction. Output arrays are reused in place; no persistent cache, component, registration, Tick, timer, or NN evaluation is added. There is no per-frame work when the node is unused. This is a callable node so Blueprint consumers can share its array outputs from one execution per frame.

Focused regression: `Prophecy.NN.RootWindow.Continuous` checks fractional curved-path sampling, yaw wrap, current-root anchoring, policy-boundary continuity for consistent predictions, horizon times, and collision/floor translation. No performance benchmark is required for installation.

Installed in a successful normal Editor build on 2026-09-15. The regression passed. `Saved/Diagnostics/TestContinuousRootWindow.py` then sampled the existing scene for 100 frames: the continuous root moved on 50 between-policy frames while the raw current root stayed unchanged; current-root error against the applied actor root was zero. Report: `Saved/Diagnostics/ContinuousRootWindowPIE.json`. Unreal was reopened and left open with test PIE stopped; authored assets were not edited or saved.

## Following the window with a velocity-driven object

Indices are spaced by the policy interval, not the render Tick interval. For a frame delta `dt <= TimeOffsetsSeconds[1]`, sample a target with `Lerp(WorldRoots[0].Location, WorldRoots[1].Location, dt / TimeOffsetsSeconds[1])`, then set velocity to `(target - object location) / dt`. Preserve the caller's desired axis mask. For larger deltas, sample the matching time segment rather than extrapolating the first segment. This predicts motion; contacts and subsequent policy changes can prevent exact tracking.

2026-09-16 investigation of unchanged `handle magic cube`: the Blueprint targeted index1 directly but divided by0.016667. Runtime capture confirmed60Hz frames, index1 at+0.033333335s and straight running speed499.9996cm/s. Last60 samples per agent: postphysics cube was within0.00156cm of index1, while its previous physics position was8.33177cm ahead of the next frame's current root—the reported comparison before velocity assignment. This is a30Hz horizon versus60Hz arrival-time mismatch, not a root-window error. No Blueprint/source changes made; user's unsaved Blueprint preserved. Evidence `Saved/Diagnostics/MagicCubeTiming.json`.

## Set Locomotion Root Window Location

`Set Locomotion Root Window Location` takes Agent (defaults Self) and World Location in Unreal centimeters. It places the actual current locomotion root low point—the continuous getter's index0—at that position immediately. All stored root positions, previous/current presentation endpoints, raw window anchors and future debug samples receive the same world translation. Rotations, times, velocities, input directions, root-relative recurrent poses and root-relative smoothing history remain unchanged. Pose snapshot world carriers are shifted under the existing lock; no skeleton decode or NN evaluation is needed.

Placement is unswept to honor the exact requested point. Later movement resumes normal collision and steering. This is a root/target move, not a teleport of native Jolt ragdoll bodies. The node returns false before initialization/window availability, for disabled inference, external bridge ownership, full attacks or active NN defenses. Locomotion during half attacks is supported; cached half-attack presentation poses follow the translation. World-space gameplay destinations remain fixed. There is no added tick, allocation for a persistent feature state, or background work when unused.

## Root magic velocity

`Set Root Magic Velocity` takes Agent, World Linear Velocity (cm/s, XYZ) and Add to Current. `Set Root Magic Ang Velocity` takes Agent, World Angular Velocity Degrees (degrees/s, Z yaw only) and Add to Current. False replaces only that term; true accumulates only that term. Setting a zero vector with Add to Current false clears the respective term. Terms are per-agent and held until updated or cleared. Neither adds an impulse to the mover.

Magic displacement is added after mover prediction and root-window smoothing. Actual locomotion advances with the same contribution while the mover retains its own linear velocity and yaw momentum. Angular magic carries the stored facing target and transports smoothed travel directions into the rotated root frame, so world-space linear motion is not rotated by magic yaw. The normal root velocity getter includes the active contribution. Vertical velocity moves the root and is represented in returned/debug root windows; the NN's existing planar trajectory feature remains planar. Explicit subsequent facing commands and world collision still apply normally. Full attacks, NN defenses, disabled inference and external bridge ownership pause the terms. Both zero removes the optional per-agent entry. No new tick, timer or NN evaluation.

User explicitly requested to perform all gameplay testing themselves on 2026-09-16. The root-location PIE test script was prepared but NOT RUN; no gameplay test or benchmark is claimed for these nodes.

`Get Root Magic Velocity` returns the configured world linear term in cm/s. `Get Root Magic Ang Velocity` returns the configured angular term in degrees/s (Z yaw, X/Y zero). They read the stored terms even while their application is paused, and return zero when unset.

`Set Root Self Balancing` now has `Magic Velocity Threshold Cm Per Second` and `Magic Ang Velocity Threshold Degrees Per Second`, each defaulting to10000. Balancing is inactive when either the XYZ magnitude of magic linear velocity or absolute magic yaw speed is strictly greater than the corresponding threshold. It can resume when both are at/below the thresholds and the existing speed/input conditions allow it. The check runs before foot sampling and performs no extra work when balancing is disabled. Existing Blueprint nodes receive the10000 defaults for their new pins.

## Crash recovery and authorized verification, 2026-09-16

After a live-patch crash in Set Root Self Balancing, the user explicitly authorized testing. The balancing state now uses a distinct native type/storage identity, avoiding reuse of retained TMap allocation with the old element layout. A normal Editor build passed and testNN was reopened. The unchanged3-agent setup passed181Jolt steps; focused tests passed setters/getters/add/clear/isolation,240 balancing state changes, root-window translation across policy updates, independent world translation and yaw, zero residual motion on clear, and threshold boundaries/reactivation/defaults. Jolt remained healthy252steps. Reports: `Saved/Diagnostics/RootMagicCurrentSetup.json`, `Saved/Diagnostics/RootMagicFocused.json`. No authored assets were modified or saved by these tests.
