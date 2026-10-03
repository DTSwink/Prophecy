# Run pinning boost

**Removed October 3, 2026, at the user's request.** Ordinary Run boost, attack-recovery boost, their getter, and the older near-floor forced minimum are removed from Unreal runtime and Blueprint APIs. The current pose Blueprint has no remaining calls; execution wiring is preserved. Run uses its decoded NN pin weights directly. Walk pin controls and foot-roll correction remain. The descriptions below are historical.

`Set Run Pinning Boost` takes Agent and Alpha (default0, range0..1). Per-agent; Alpha0 removes its setting and leaves existing behavior exactly unchanged. No timer, blend history, extra inference or bone traversal.

After Run sigmoid decoding and its existing near-floor minimum rule, select the larger pin and replace it with `lerp(pin,1,Alpha)`. Leave the smaller unchanged. An exact tie chooses left deterministically. Example0.2/0.6 at Alpha0.5 becomes0.2/0.8; Alpha1 becomes0.2/1.0.

Applied before Run foot-roll position correction. In Walk/Run regional recovery it affects the Run contribution before ordinary region mixing. Walk bounds/smoothing/transfer logic is unchanged. Raw pin readback remains pre-control decoding; effective readback includes the boost and subsequent policy mix. Foot clamps, floor correction and knee smoothing may still move a fully pinned foot; this is a pin-weight control, not a world-space foot lock.

Storage lives beside existing pin controls without changing retained agent/pose layouts. World cleanup removes settings. Alpha outside0..1 or nonfinite is rejected without changing existing configuration. Disabled fast path skips lookup when no agent uses it and does no pin arithmetic. Existing run/locomotion paths only; no new attack or defense pin decoder.

## Removal validation, 2026-10-03

Normal Development Editor build succeeded. Cold-loaded TestNN verifies all four retired APIs absent and the pose Blueprint compiling with preserved wiring. All 14 focused tests passed (Armed gate, attack counter, regional ownership, Walk pinning and root window). An owned 265-tick scene replay passed finite pin checks; 155 visible pure-Run samples before the first attack have exactly equal decoded/applied pin weights. Later regional recovery can mix independently controlled Walk legs, so that interval is excluded from the pure-Run equality assertion. Evidence: `Saved/Diagnostics/RemoveRunPinBoost20261003/`.

## Historical validation, 2026-09-25

Live Coding build succeeded124.07s, loaded2026-09-24 23:47:01UTC. Canonical reflected SetRunPinningBoost call resolves; the existing Python wrapper was stale after reload, so verification used the current class default object. All8 RunPinning/WalkPinning tests passed23:47:49UTC: winner selection, exact Alpha1/0, partial interpolation, ties, per-agent isolation, invalid-alpha rejection, no timer registration and world cleanup. Existing Walk controls pass unchanged. Pose Blueprint inspection status3/zero stale native/pin types/wiring preserved. No gameplay rollout, graph edit, explicit save or restart. Include this Live Coding patch in the next authorized normal editor build.
