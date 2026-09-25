# Supporting knee jiggle near tick 190

2026-09-25. Current scene performs kickL; the non-kicking right leg jiggles during recovery. This extends the [independent knee recovery](LegRecoveryTimingAndPelvis360.md) without changing the accepted historical solver, pole guidance, recovery duration or turn speed.

## Cause

The independent pole timer is still active throughout the event (145 exit, protected window through205). The policy knee bend decreases smoothly toward194, then increases. However, presentation interpolates the two policy poses while `ApplyRigidCalves` repairs the knee using the **latest live** calf-return length. At193 that applies45.648cm to a pose still halfway between calf lengths43.767 and45.648cm. At195 the length changes in the opposite direction. That mismatch introduces repeated bend reversals, even without physical simulation.

## Correction

While calf recovery is active, sample its length from the previous/current published calf-to-ankle distances using the **same interpolation alpha as the pose**. Then use the existing connected knee repair. Existing snapshots contain everything required: no new retained pose data, clock or inference. Missing snapshot endpoints retain the old fallback for nonstandard sources. Alpha1 uses the exact current endpoint; disabled interpolation remains supported.

All production readers pass their actual alpha: skeletal animation, authored single-bone queries and full physical-target queries. Physical foot-drive clamping also uses the already-presented signed calf length during recovery rather than re-reading the newest return clock. Outside recovery its original reference endpoint and leeway remain unchanged. Physical joint limits are unchanged.

This does not extend the leg timer, alter its pole target, change policy reconstruction or smooth the pelvis/foot path. Existing optional knee-pop smoothing runs afterward; it can make tiny additional endpoint changes because the repaired knee is different. Physical feedback can still make later simulated rollouts diverge. No extra interpolation/bone work is performed when calf recovery is inactive.

## Controlled evidence

`CaptureLeg190Paired.py` runs the unchanged scene with the old presentation behavior and reads old/new authored targets consecutively **within the same frame**. No world/NN advance occurs between reads. Right knee bend in degrees:

| Tick | Old | Corrected |
| --- | ---: | ---: |
| 191 |35.304|34.711|
| 192 |26.541|27.029|
| 193 |29.958|24.637|
| 194 |21.456|21.734|
| 195 |17.172|22.907|
| 196 |23.595|23.947|
| 197 |26.442|27.961|
| 198 |29.520|29.519|
| 199 |26.651|31.245|
| 200 |31.304|31.303|

Over189–201, bend total variation decreases60.290→39.659degrees, maximum second difference12.181→5.724degrees/tick². Pelvis and left-foot positions/rotations are identical; right-foot rotation is identical and position differs at most0.00264cm through the subsequent optional correction. Do not describe this as an exact endpoint-invariance guarantee for every downstream feature.

A separate300-tick replay with corrected presentation enabled from startup reproduces these corrected values, including the second kick exit. This is a bounded fix for the recorded temporal mismatch, not a claim that all possible knee motion is perfectly smooth.

After the physical-drive follow-through, `Leg190-final-drive.json` completes300 ticks again. All captured authored bone positions180–205 match the preceding corrected replay exactly (maximum difference0cm).

## Validation

Initial Live Coding build13actions/243.79s loaded14:41:57UTC. Ten focused native tests passed14:43:08UTC, including the extended recovery-calf test covering0/.25/.5/.75/1 interpolation, both legs, endpoints, repeat-read stability despite newer live return values, and inactive cleanup. Physical-drive follow-through build3actions/69.68s loaded14:44:58UTC; RecoveryCalfLength, FootTargetLeeway, FrameCadence and SharedReadersAndLifecycle passed14:45:25UTC. An overlapping owned capture ended early during automation cleanup and is not evidence; the final capture was restarted after the test queue completed.

Evidence: `Saved/Diagnostics/Leg190-live.json`, `Leg190-frozen.jsonl`, `Leg190-paired.json`, `Leg190-final.json`, `AnalyzeLeg190Paired.py`, `Leg190-paired-summary.json`. Editor diagnostic `Prophecy.Recovery.LengthInterpolation`:1=corrected(default),0=old presentation. It is restored to1 after captures. No Blueprint graph/settings/assets edited or saved, no restart or push. All diagnostic PIE sessions were owned and ended.
