# Slash-train foot teleport at the first slashRU

Confirmed numerically in the user's kinematic setup with their magic-cube influence removed. Seed2026092223 reaches its first slashRU at game tick148 (viewer reference first slashRU starts at NN frame62). At tick149, the displayed left/right foot steps were14.690/15.059cm.

## Cause

At attack end, the root first catches up and then moves to the selected self-balancing return point. `SetAgentLocomotionRootWindowLocation(..., true)` preserved the encoded recurrence and the published world-pose store, but did not rebase `ComponentTransformBuffer`, `PreviousComponentTransformBuffer`, or their local root transform. The Blueprint starts its next attack before another locomotion publication; `TriggerNNAttack` seeds from those stale component caches using the new carrier.

All nine measured lower-body bones therefore gained exactly **(-1.692124,-14.131355,0)cm** in their previous-frame world positions. The14.232304cm common translation equals the second root correction (independently reconstructed from catch-up and return locations to1.5e-6cm). The rendered pose had remained fixed at tick148; the error became visible on the new attack's first publication at149. Pelvis entry inertia concealed much of its own display step, but did not hide the feet.

This is a coordinate-cache error, not a foot pin command or knee reconstruction change. In the viewer, reference feet move1.839/7.025cm across61→62; there is no equivalent stale-carrier shift. Exact NN motion need not match because the initial poses and local gameplay rules differ.

## Correction and controlled test

The preserve-world-pose translation now offsets both cached component endpoints into the new root frame and updates the local top-level bone. Bone rotations/scales, published world targets, calf/pole reconstruction, clamps and pinning are unchanged. Ordinary explicit root translations with preservation disabled are unchanged. Work occurs only when a nonzero preserving root translation is requested; no new timer, inference or per-frame callback.

Development-only `Prophecy.RootTranslation.CachedPoseRebase` defaults1;0 is the diagnostic old behavior. Shipping always applies the fix. For the causal replay it remained0 through tick147, then changed to1 immediately before the disputed boundary:

| Measurement | Before | Corrected |
|---|---:|---:|
| Maximum published-position difference through147 | — | **0cm** |
| Shared cached-frame translation at149 |14.232304cm|0.00000143cm|
| Displayed left foot148→149 |14.690cm|0.623cm|
| Displayed right foot148→149 |15.059cm|3.531cm|

The error is removed at the same event with the preceding rollout exactly unchanged. A second235-tick replay with the fix enabled throughout checks all five subsequent handoffs through pike: maximum previous/current cache discontinuity0.00001034cm. This verifies this coordinate jump; it does not certify the entire30-attack rollout's visual parity.

Evidence: `Saved/Diagnostics/SlashTrainFeet-{baseline,late147,fixed}.json` and corresponding `-nn.jsonl`, `AnalyzeSlashTrainFeet.py`. All owned captures ended, trace frames0, comparison switch1, capture arrays released. No user Play was interrupted and no asset saved.

Live Coding build336.66s succeeded2026-09-25 and loaded19:54:58UTC, including the optional kick checkpoint control. A stale library default exposed by reloading was repaired with the existing editor helper:70 archived defaults corrected, Blueprint status3, other values/wiring preserved, unsaved. Include native changes in the next authorized normal build before restart.
