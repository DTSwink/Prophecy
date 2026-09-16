# Root/cube bounds runaway — diagnosis, 2026-09-16

**Fixed and installed later the same day.** Automatic bounds now request pose-preserving root recentering. Both lower/upper recurrent frames, publication endpoints and retained physical-feedback history are translated into the new root coordinates; upper base/pelvis features are rebuilt. Cached NN world targets, half-attack visible world poses and Jolt target history remain unchanged. The whole root window and registered cube still receive the same correction. Explicit whole-pose placement retains its previous behavior.

Verified with the same10-second current-scene replay, bounds50cm and root cap900cm/s still enabled: moving-root peak measured speed893.97cm/s (previous209,188.19), root net travel3,488cm (previous945,140), physical pelvis peak speed1,018.8cm/s (previous209,766.5). No runaway. The maximum post-physics root/pelvis gap was59.1cm because bounds sample the previous completed physics pose before the next step. These limits control the root, not every physical limb velocity. Evidence fixed.json and comparison.json beside the original captures. Live Coding succeeded; no restart, Blueprint edit or asset save.

Current Blueprint audited read-only via Prophecy.Sword.AuditCollisionGraph. Set Root Pelvis Bounds is enabled at50cm with the Magic Cube registered. Set Root Velocity Limits is enabled at900cm/s and1000deg/s. Handle magic cube sets magic channel1 to horizontal (cube-root0)*0.2/0.016667, and overwrites cube velocity with horizontal (root1-cube)*0.5/0.016667. A separate channel2 becomes approximately (16.93,717.02,-0.216)cm/s on the moving pawn. The continuous getter still returns root1 at1/30s.

Reproduced using current scene with no Blueprint edits. Ten-second PIE captures sampled roots, physical pelvis and velocity, cube location/velocity, settings, magic channels, root window, and (second capture) authored pelvis targets. A/B overrides were PIE-only, reapplied after each frame; each run ended PIE. No source/asset fix installed.

## Measurements

Moving pawn root travel over10s (rounded):

- Current setup:945,140cm (9.45km), peak physical pelvis speed209,766cm/s.
- Same with cube registration cleared:1,482,245cm. Cube feedback gets worse, but is not required for the runaway.
- Same with speed limits disabled:1,204,781cm. The limiter is not required either.
- Same with pelvis-and-below feedback tolerance1,000,000:911,053cm. Lower feedback is not required.
- Same with pelvis bounds disabled:2,763cm, peak moving-pawn pelvis speed1,007cm/s. This removes the runaway. A separate pawn still shows unrelated post-contact vertical motion in that run; this is not a claim that the whole scene is perfect.

At tick50 in the current setup, displayed root is approximately(-3,-266,-0.5)cm; the authored pelvis target is(-9,-341,73)cm and physical pelvis(-9,-341,71)cm. At tick120 the root is(970,-14283,-0.8), target(1001,-14735,99), physical pelvis(1001,-14735,97). Physics follows its authored target closely while both accelerate away. The mover velocity readback remains around687cm/s; the extra displacement is the bounds teleport, intentionally outside the cap. The independent Magic Cube correction preserves the root/cube relative offset, so channel1 is approximately zero during the large runaway rather than driving it.

## Cause

ProphecyRootPelvisBounds::Apply uses SetAgentLocomotionRootWindowLocation to recenter the root around the physical pelvis. That placement function translates root/prediction history AND cached world pose carriers (FProphecyNNPoseStore::TranslateAgentWorldPose), while keeping root-relative recurrent poses unchanged. The physical bodies are not teleported.

Consequently it also translates the NN pelvis target toward/beyond the physical pelvis. The magnetized pelvis follows that shifted target, leaving the root outside the circle again. A persistent root-relative target offset larger than the radius has no stable solution under this operation; growing predicted offset makes it accelerate. Example: pelvis target60cm behind root with radius50: move root back10cm, but also move target back10cm; physics follows, restoring the original60cm gap. Repeat. This is a feedback loop introduced by using whole-pose relocation for pelvis-based root recentering.

The authored-target history was inspected as an alternative cause. Its trajectory interpolation may affect a discontinuity, but the actual target positions above already demonstrate the persistent moving-target loop; no inference about fake target velocity is needed.

## Proposed correction (not implemented)

Give automatic pelvis bounds a root-recentering path: shift root and every root-window/history sample by the common offset, and shift the registered cube as requested, while preserving current/previous world-space NN body targets. Rebase root-relative recurrent/presentation state into the new root frame so the pelvis/feet targets are not dragged away. Upper input must use that coherent rebased lower/pelvis state. Retain ordinary explicit whole-pose placement semantics separately. Shifting only the cached render pose or simply capping teleport distance would not address the underlying recurrence.

Evidence: Saved/Diagnostics/RootCubeRunaway/{baseline,targets,no_cube_shift,no_bounds,no_caps,no_feedback}.json and capture.py. Final editor PIEoff; no authored assets intentionally modified or saved.
