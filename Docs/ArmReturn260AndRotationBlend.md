# Right-arm kickback and rotation controls — 2026-09-26

## Detected cause and correction

Unchanged current pike replay reproduced the reported instability around260. The actual target jumps36.078cm at253,29.068cm at255, then rebounds. The presented hand moves up to18.657cm in one game tick. This is in the authored target before physics.

`ClearFrontPath` tested torso clearance in actual torso coordinates but computed front/back winding and the fallback arc in the selected return reference. After switching that reference to root rotation, its rear azimuth seam no longer matched the body's back. At the second return, the NN destination crosses that false seam; a short clear segment suddenly becomes a long front-wrap route. Sword clearance/arm reach then compound the displacement and it feeds the next NN prediction.

Route winding, exclusion ellipse, straight/curved transition and arc-length speed bound now all use actual torso coordinates. Results transform back into the selected reference before storing/using the wrist. This does not restore torso carrying: the stored wrist still follows the selected position and rotation frame. Only the obstacle geometry is body-relative. Existing blade winding, clearance, reach, elbow reconstruction, duration and handoff remain intact.

## Spine-mode restoration after regression

**September 26 current behavior:** at the user's explicit request, unchecked/spine-position returns again use the original anatomical torso carrier and clavicle-mounted idle arm. Calling the rotation-blend node no longer overrides that mode. Its Spine Local Rotation Blend pin remains present for Blueprint compatibility but has no effect. Pelvis-position returns retain the Pelvis Local Rotation Blend control. The earlier two-control description below is historical for spine mode, and the existing UFUNCTION tooltip may still reflect it; no reflected signature was changed during this restore.

The original solver rollback alone was insufficient because the new reference selection also changed the idle hinge fed into it. The current SlashR setup used Spine Local Rotation Blend 1, all pelvis-position checkboxes false. In the causal comparison (`slashr_root_one` vs `legacy_spine_late` under `Saved/Diagnostics/ArmReach`), all future bone positions matched exactly through tick 125. Original reference restored immediately before the first return: right upper-arm accumulated signed twist ticks 126–179 changed −271.123 → +63.800 degrees; peak sample step 28.194 → 8.484 degrees. Second return 216–269 changed −285.025 → +62.419 degrees, peak 29.226 → 8.508. Later states differ recurrently; the exact prefix establishes the first-return comparison. These are bounded measurements, not a claim of no remaining motion or universal collision clearance.

`UsesControlledReference` now returns only `UsesPelvisReference`. There is no runtime comparison switch or new inactive work; the temporary LegacySpineReference diagnostic was removed from source. Stable pins, per-attack position selection, both-arm selection, durations and pelvis-mode rotation remain. Updated regression verifies that none of the five sampled Spine weights overrides the original mode and that explicit pelvis mode still uses its independent weight.

Restoration loaded via Live Coding at 18:01:43 UTC, build 50.88 seconds; all 13 current arm/core tests passed at 18:02:31 UTC (two stale registrations also ran). No asset save or editor restart. Include source in the next authorized normal build.

## Original node introduction (spine override now reverted)

**Set Attack Arm Return Rotation Blend** takes Agent and:

- **Spine Local Rotation Blend**, default0.
- **Pelvis Local Rotation Blend**, default1.

Each value is clamped to0–1:0 means anatomical pelvis rotation,1 means current root rotation, intermediate values use quaternion slerp. The per-attack `Set Attack Arm Return Pelvis Local` selection determines which value applies and which position mode is used. Both returning hands, their neutral destination and prior hinge transport share the selected frame. Body clearance always uses the actual torso.

Before the new node is called, existing settings are preserved: original torso orientation for spine mode and root orientation for pelvis mode. Calling it explicitly opts the spine mode into the pelvis-to-root rotation control as well. Pelvis bone axes are calibrated to anatomical axes once per return. Spine-position mode retains the actual anatomical torso origin; pelvis-position mode retains its calibrated chest-height offset above pelvis, oriented by the selected rotation.

Call before attack or inside Special Ended. Values latch before the first returned pose; changing them during an initialized return affects the next return and cannot reinterpret an already moving wrist. Reset snapshots preserve both values and cancel live return state. New specials/cancellation/world cleanup clear active calibration. No node is automatically wired. No new timer, inference or inactive pose work; all frame sampling remains inside the existing active-return block.

## Validation

- Live Coding build165.75s, loaded15:44:28UTC.13 current native tests pass15:45:13UTC (one obsolete historical test remains registered and is excluded). New regression checks coordinate-invariant obstacle routing, false-seam crossing, weights0/.25/.5/.75/1, separate spine/pelvis values and origins, per-agent isolation, latching, reset and cleanup.
- Causal replay `instability260` vs `route_latefix`: start with old geometry, switch only routing at252. Every recorded future bone position matches exactly through252. Target step25336.078→3.994cm;25529.068→3.729cm. Remaining steps decrease to1.384cm at269 instead of rebounding. Largest presented step in240–26918.657→2.343cm. This directly tests the reported state instead of relying on an altered earlier rollout.
- Full final360-tick replay `body_route`: largest presented step in240–2692.236cm. First pike retains the straightened route: right world deviation4.229cm (previous3.836cm, before root rotation28.911cm). Neither arm straightens fully: first-return minimum left29.14/right20.88degrees. Sampled swept blade clearance1.453>1 (previous1.181). This is bounded replay evidence, not a guarantee for every possible pose/setting.
- New node reflected/callable; Blueprint library defaults repaired after reload, values/wiring preserved, no explicit save. Owned diagnostic Play ended, Audit0, BodyRoute1, Refined1. No user Play interrupted, Blueprint rewired, restart or push. Include the patch in the next authorized normal build.

Evidence under `Saved/Diagnostics/ArmReach`: `instability260`, `route_latefix`, `body_route`, `compare260_body_route`, `compare_body_route`. Scripts: `DiagnoseArm260.py`, `CaptureArmReach.py`, `CompareArm260.py`, `CompareArmReach.py`. Editor-only `Prophecy.SlashReturn.BodyRoute=0` restores the diagnosed geometry for exact-state testing; default1 is the fix and Shipping always uses the fix.
