# Unpinned knee recovery

Rejected experiment, rolled back in source 2026-09-24.

The user reported worse flexion jiggle. The free-calf projection and its candidate-only test have been removed; the reach guard remains. The numerical improvement below concerns a selected near-straight dip and did not establish overall smoothing. Short four-tick supporting-knee reversals16.17/17.87/15.01degrees remained unchanged. Evidence: `Saved/Diagnostics/KneeFlexReversals-comparison.json` and `MeasureKneeFlexReversals.py`. Rollback build succeeded55.36s; loaded successfully22:02:52UTC. The following records the rejected experiment, not the current solver.

## Diagnosis

After the Walk reach guard removed the pinned extension events, the current repeated kickR setup still produced a short left supporting-knee collapse. The effective left pin was zero throughout frames249–270. At frame262 the presented knee was only4.22 degrees bent, between49.47 degrees at256 and26.35 degrees at268. Extending the pin cooldown cannot address an already unpinned foot.

After tempering finished, the remaining signed calf-length return held the NN ankle endpoint and reconstructed the knee. The NN requested a longer calf than the returning connected chain: frame259 raw knee23.28 degrees became6.26 degrees after correction; frame261 raw9.11 became0.80 degrees in the published policy pose. The correction amplified the source extension. The NN is recurrent, so these source poses also incorporate earlier corrections; this is not evidence that the checkpoint alone caused the problem.

## Change

In the existing calf-length-return branch, when no leg tempering or regional pelvis mismatch requires a different reconstruction, project the ankle from the current policy knee along its calf direction to the returning calf length. Weight this adjustment by one minus the effective pin. Full pins retain their endpoint authority, free feet retain their policy bend when floor/reach feasible, and partial pins interpolate continuously. Then perform the existing connected/floor solve.

The user's disabled outer clamp remains respected. Existing knee guidance, inner reach, foot rotation, pelvis, attack output and return clock are unchanged. No new timer, state, inference, family gate or normal-path processing. The projection runs only inside the already active length-return branch.

## Validation and limits

Final Live Coding build succeeded59.93s and loaded21:55:10UTC; all28 focused native tests passed21:57:24UTC. The new FreeCalfLength fixture verifies partial-pin continuity, full-pin identity, source-knee preservation where feasible, connected segment lengths, floor clearance, unchanged pelvis and foot orientation. Existing pinning, tempering, recovery, joint and reset tests also passed. Pose Blueprint compiled; no Blueprint/map edits or explicit asset saves/restart.

Unchanged user setup replayed602 frames with five recovery episodes. At frame262 the knee bend improves4.22→23.07 degrees. For the affected second episode, late recovery's largest bend step falls15.78→7.72 degrees/frame and its change in bend step14.56→3.97 degrees/frame. Windows terminate at the next attack rather than counting attack frames as recovery.

This is not a universal smoothing claim. Fifth-episode late bend step rises7.15→10.16 degrees/frame; over all locomotion samples after2 seconds maximum thigh step is15.97→16.27 degrees while knee swivel step falls18.05→14.52 degrees. Smaller flex/return motions remain. No global motion filter was added to hide them.

Confirmed pure-Walk published samples retain floor clearance within floating-point error (minimum -0.0000021cm). The independent Walk geometry oracle excludes single-Run switch samples whose weight metadata still describes the prior recovery; it does not certify all mixed-policy or rendered floor contacts. Existing solver floor projection and native tests remain in place.

Evidence under Saved/Diagnostics:

- CalfAnkleConnection-pin-jiggle-current.json, -pin-jiggle-free-calf.json and -pin-jiggle-final.json; matching FootVibration-nn JSONL files.
- UnpinnedJiggle-analysis.json; FreeCalfReturn-comparison.json; FreeCalfReturn-verification.json.
- AnalyzePinJiggle.py, ExplainUnpinnedJiggle.py, CompareFreeCalfReturn.py and VerifyFreeCalfReturn.py.

Owned Play ended; tracing disabled and captured editor memory released. Unreal remains open. Do not restore this rejected patch in the next normal build. No push requested for this follow-up.

Rollback verification:602-frame unchanged-scene replay `pin-jiggle-rollback` exactly matches pre-experiment physical transform components (maximum error0), confirming the rejected runtime change is gone. Evidence: `Saved/Diagnostics/KneeJiggleRollback-verification.json`. Owned Play ended, trace off, capture memory released. Short flexion jiggle remains unresolved.
