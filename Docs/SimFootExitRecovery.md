# Simulated foot pop at special exit

2026-09-25, current user setup (Physical/Jolt). No Blueprint or scene changes.

## Cause

Current tick Blueprint sets Set Physical Foot Target Clamp Leeway to1000cm for Attack; locomotion remains default0. The kinematic calf-length recovery already preserves the outgoing foot distance and blends it to rest. The Jolt target-packet builder instead immediately clamps the foot drive to `Calf.TransformPosition(reference foot offset)` when the mode returns to locomotion. Its target and feedback therefore jump while the visible authored pose is still recovering.

Initial1581-row20–1600 capture reproduces exits across overs, jabs, hooks and kicks. jabL exit580 has smooth authored left-foot step0.972cm but estimated rest-clamped drive step5.012cm. Error to kinematic target grows4.420→4.981cm at that exit. Prior4cm mismatch already exists during the attack; this is not entirely new error at exit.

Transient causal test changes only locomotion physical-target leeway at244, after the recorded overR prefix. Every captured physical bone position20–244 is identical. At245 left-foot error increases4.111→4.144cm instead of4.111→4.897cm, isolating the clamp change.

## Fix

Jolt's physical foot target now uses the same signed returning calf-length delta as kinematic presentation when constructing the calf endpoint. Both extension and compression return smoothly on the existing finite recovery clock. The configured physical-foot leeway is still applied around that endpoint. When the length return finishes the endpoint is exactly its old rest value; inactive delta0 returns the original endpoint directly.

This applies to shared full-special recovery (non-kick attacks/parry/dodge), not just jabL. Active kick joint allowance still bypasses the physical target clamp exactly as before. Leg reconstruction's diagnostic disable suppresses this corresponding endpoint adjustment too. No joint limit/rotation/magnetisation/gain/solver-iteration/Blueprint or NN changes. Published target history and feedback use the corrected target through the existing common packet path. No new tick callback, clock, retained recovery state or additional inference.

Editor-only `Prophecy.PhysicalFoot.RecoveryLength`0=legacy,1=final/default; non-editor always final. `Prophecy.PhysicalFoot.TraceFrames` is an opt-in possessed-agent target packet trace, normally0.

## Validation

First compile found a test-local shadowed variable; renamed it. Successful incremental build23.83s, loaded00:29:34UTC Sep25. All5 PhysicalFootTargetLeeway, RecoveryCalfLength, KickFootLeeway and native joint/rig FootExtension tests pass00:29:49UTC. New endpoint checks cover signed return, zero exact bypass, configured leeway,60-tick smooth convergence and rotated coordinate frames.

Paired simulation leaves legacy behavior enabled through244, then final1 for245 onward. Every captured physical bone position20–244 matches exactly (0cm error). Native published drive logs at245:

| Measurement (cm) | Legacy | Fixed |
| --- | ---: | ---: |
| Left authored foot step |0.515886|0.515886|
| Left drive target step |5.267551|0.511474|
| Drive vs authored foot |4.892731|0.006574|
| Physical foot step |1.171923|0.470557|
| Change in physical-minus-authored displacement |0.859860|0.122276|

At246 the drive vs authored distance is0.0000037cm. The existing roughly4.1cm physical/authored separation remains immediately after exit because the simulated connected leg does not freely reproduce the checkpoint's stretched/compressed chain. This fix removes the additional target discontinuity, not all physical tracking error. Joint limits remain unchanged.

Evidence: Saved/Diagnostics/SimFootExit-capture.json/-metrics.json; SimFootExitNoClamp-capture.json; SimFootLegacy-capture.json/-drive.log; SimFootPaired-capture.json/-drive.log; SimFootRecovery-comparison.json.

Final default-behavior replay completed ticks20–1600 (1581 rows), entirely Physical mode, all recorded transforms finite. The attack sequence and exit ticks remain the same. At jabL580, change in physical-minus-authored displacement falls0.570196→0.142118cm, with authored motion effectively unchanged0.972218→0.972213cm. Existing physical separation remains4.456cm. Kick exit error-step measurements agree within0.00023cm; the active kick path was not changed. This is bounded evidence for the current scene, not proof of perfect tracking for arbitrary settings. Results in SimFootFinal-capture.json and SimFootFinal-summary.json.

Owned diagnostic PIE ended. No Blueprint/scene edits or saves. Live changes still require inclusion in the next authorized normal editor build before restart.
